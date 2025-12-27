#!/usr/bin/env python3
import os
import tarfile
import sys
from pathlib import Path

import boto3
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

from logger_config import setup_logger

load_dotenv()

logger = setup_logger("recovery_worker")

# Use absolute paths based on script location
SCRIPT_DIR = Path(__file__).parent.resolve()

S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
AWS_REGION = os.getenv("AWS_REGION", "auto")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")

# Directory for restoration
RESTORE_ROOT = SCRIPT_DIR / "recovery_output"


def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte URL-safe base64 key from the password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def download_from_s3(object_name: str, local_path: Path) -> bool:
    """Downloads the file from Cloudflare R2 / S3."""
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        logger.info(f"Downloading {object_name} from {S3_BUCKET}...")
        s3_client.download_file(S3_BUCKET, object_name, str(local_path))
        logger.info("Download successful.")
        return True
    except Exception as e:
        logger.error(f"Failed to download from S3: {e}")
        return False


def decrypt_backup(encrypted_path: Path, output_path: Path) -> bool:
    """Reads salt, derives key, and decrypts the file."""
    if not BACKUP_PASSWORD:
        logger.critical("BACKUP_PASSWORD environment variable is missing!")
        raise ValueError("BACKUP_PASSWORD environment variable is missing!")

    logger.info(f"Decrypting {encrypted_path}...")

    try:
        with open(encrypted_path, "rb") as f:
            # 1. Read the first 16 bytes (Salt)
            salt = f.read(16)
            # 2. Read the rest (Encrypted Data)
            encrypted_data = f.read()

        # 3. Derive key using the extracted salt
        key = derive_key(BACKUP_PASSWORD, salt)
        fernet = Fernet(key)

        # 4. Decrypt
        decrypted_data = fernet.decrypt(encrypted_data)

        # 5. Write to output file
        with open(output_path, "wb") as f:
            f.write(decrypted_data)

        logger.info(f"Decryption successful: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Decryption failed (Wrong password?): {e}")
        return False


def safe_extract_filter(member: tarfile.TarInfo, path: str) -> tarfile.TarInfo | None:
    """
    Filter for tar extraction to prevent path traversal attacks.
    Rejects members with absolute paths or paths containing '..'.
    """
    # Reject absolute paths
    if member.name.startswith('/') or member.name.startswith('\\'):
        logger.warning(f"Skipping absolute path in archive: {member.name}")
        return None

    # Reject path traversal attempts
    if '..' in member.name:
        logger.warning(f"Skipping path traversal attempt in archive: {member.name}")
        return None

    # Resolve the final path and ensure it's within the extraction directory
    dest_path = Path(path) / member.name
    try:
        dest_path.resolve().relative_to(Path(path).resolve())
    except ValueError:
        logger.warning(f"Skipping file that would extract outside target: {member.name}")
        return None

    return member


def extract_archive(tar_path: Path, extract_to: Path) -> bool:
    """Extracts the tar.gz archive safely."""
    logger.info(f"Extracting {tar_path} to {extract_to}...")
    try:
        extract_to.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar_path, "r:gz") as tar:
            # Use filter for safe extraction (Python 3.12+) or fallback
            try:
                tar.extractall(path=extract_to, filter=safe_extract_filter)
            except TypeError:
                # Python < 3.12 doesn't support filter parameter
                # Manually filter members
                safe_members = []
                for member in tar.getmembers():
                    if safe_extract_filter(member, str(extract_to)) is not None:
                        safe_members.append(member)
                tar.extractall(path=extract_to, members=safe_members)

        logger.info("Extraction successful.")
        return True
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return False


def main(backup_filename: str) -> int:
    """Main restore workflow. Returns 0 on success, 1 on failure."""
    # Convert to Path and resolve relative to script directory if not absolute
    backup_file = Path(backup_filename)
    if not backup_file.is_absolute():
        backup_file = SCRIPT_DIR / backup_filename

    local_encrypted_file = backup_file
    decrypted_tar_file = backup_file.with_suffix('').with_suffix('.tar.gz') if backup_file.suffix == '.enc' else backup_file.parent / backup_file.name.replace('.enc', '')

    # 1. Check if file exists locally; if not, try to download
    if not local_encrypted_file.exists():
        logger.info(f"File {local_encrypted_file} not found locally. Attempting S3 download...")
        if not download_from_s3(backup_filename, local_encrypted_file):
            logger.error("Could not find backup file.")
            return 1

    # 2. Decrypt
    if not decrypt_backup(local_encrypted_file, decrypted_tar_file):
        return 1

    # 3. Extract
    if not extract_archive(decrypted_tar_file, RESTORE_ROOT):
        return 1

    # Success summary
    logger.info("\n" + "=" * 40)
    logger.info("✅ RECOVERY COMPLETE")
    logger.info("=" * 40)
    logger.info(f"Files have been extracted to: {RESTORE_ROOT}")
    logger.info("Contents:")
    logger.info(f"  - Database Dump: {RESTORE_ROOT / 'vaultwarden.dump'}")
    logger.info(f"  - Data Directory: {RESTORE_ROOT / 'data'}")
    logger.info("\nTo finish restoration, you need to:")
    logger.info("1. Restore the Postgres dump (e.g., pg_restore -d vaultwarden vaultwarden.dump)")
    logger.info(f"2. Copy the contents of '{RESTORE_ROOT / 'data'}' to your actual data volume.")
    logger.info("=" * 40)

    # Cleanup decrypted tarball
    if decrypted_tar_file.exists():
        decrypted_tar_file.unlink()
        logger.info(f"Cleaned up decrypted archive: {decrypted_tar_file.name}")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Usage: python restore.py <backup_filename_on_s3_or_local>")
        sys.exit(1)
    target_file = sys.argv[1]
    sys.exit(main(target_file))
