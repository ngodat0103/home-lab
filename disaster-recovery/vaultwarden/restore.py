import os
import tarfile
import boto3
import base64
import sys
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from logger_config import setup_logger
from dotenv import load_dotenv
load_dotenv()
logger = setup_logger("recovery_worker")

S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
AWS_REGION = os.getenv("AWS_REGION", "auto")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")

# Directories for restoration
RESTORE_ROOT = "recovery_output"


def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte URL-safe base64 key from the password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def download_from_s3(object_name, local_path):
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
        s3_client.download_file(S3_BUCKET, object_name, local_path)
        logger.info("Download successful.")
        return True
    except Exception as e:
        logger.error(f"Failed to download from S3: {e}")
        return False


def decrypt_backup(encrypted_path, output_path):
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


def extract_archive(tar_path, extract_to):
    """Extracts the tar.gz archive."""
    logger.info(f"Extracting {tar_path} to {extract_to}...")
    try:
        os.makedirs(extract_to, exist_ok=True)
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=extract_to)
        logger.info("Extraction successful.")
        return True
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return False


def main(backup_filename):
    # Filenames
    local_encrypted_file = backup_filename
    decrypted_tar_file = backup_filename.replace(".enc", "")

    # 1. Check if file exists locally; if not, try to download
    if not os.path.exists(local_encrypted_file):
        logger.info(f"File {local_encrypted_file} not found locally. Attempting S3 download...")
        if not download_from_s3(local_encrypted_file, local_encrypted_file):
            logger.error("Could not find backup file.")
            sys.exit(1)

    # 2. Decrypt
    if not decrypt_backup(local_encrypted_file, decrypted_tar_file):
        sys.exit(1)

    # 3. Extract
    if extract_archive(decrypted_tar_file, RESTORE_ROOT):
        # Using print for final summary to ensure it stands out regardless of log level
        logger.info("\n" + "=" * 40)
        logger.info("✅ RECOVERY COMPLETE")
        logger.info("=" * 40)
        logger.info(f"Files have been extracted to: {os.path.abspath(RESTORE_ROOT)}")
        logger.info("Contents:")
        logger.info(f"  - Database Dump: {os.path.join(RESTORE_ROOT, 'vaultwarden.dump')}")
        logger.info(f"  - Data Directory: {os.path.join(RESTORE_ROOT, 'data')}")
        logger.info("\nTo finish restoration, you need to:")
        logger.info("1. Restore the Postgres dump (e.g., pg_restore or psql < vaultwarden.dump)")
        logger.info(f"2. Copy the contents of '{RESTORE_ROOT}/data' to your actual data volume.")
        logger.info("=" * 40)

    # Optional: Cleanup decrypted tarball
    # os.remove(decrypted_tar_file)
if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Use logger for usage error to keep formatting consistent
        logger.error("Usage: python restore_worker.py <backup_filename_on_s3_or_local>")
        sys.exit(1)
    target_file = sys.argv[1]
    main(target_file)