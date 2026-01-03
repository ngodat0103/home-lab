#!/usr/bin/env python3
import os
import sys
import tarfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

import boto3
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from logger_config import setup_logger
from backup_db import backup_postgres
from backup_data import backup_vaultwarden_data

logger = setup_logger("backup_worker")

# Use absolute paths based on script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKUP_DIR = SCRIPT_DIR / "backup"

S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
AWS_REGION = os.getenv("AWS_REGION", "auto")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")
MAX_BACKUPS_TO_KEEP = int(os.getenv("MAX_BACKUPS_TO_KEEP", "7"))

BACKUP_SOURCE_DB = BACKUP_DIR / "db" / "vaultwarden.dump"
BACKUP_SOURCE_DATA = BACKUP_DIR / "data"


def check_dependencies() -> bool:
    """Check all required dependencies before starting backup."""
    logger.info("\n" + "=" * 70)
    logger.info("DEPENDENCY CHECK")
    logger.info("=" * 70)

    all_checks_passed = True

    # Check 1: Required executables
    logger.info("\nChecking required executables...")
    executables = {
        "pg_dump": "PostgreSQL dump utility (required for database backup)"
    }

    for exe, description in executables.items():
        if shutil.which(exe):
            logger.info(f"  [OK] {exe:15s} - Found")
        else:
            logger.error(f"  [FAIL] {exe:15s} - NOT FOUND ({description})")
            all_checks_passed = False

    # Check 2: Required environment variables
    logger.info("\nChecking required environment variables...")
    required_env_vars = {
        "BACKUP_PASSWORD": "Encryption password for backup",
        "S3_BUCKET": "S3 bucket name",
        "S3_ENDPOINT": "S3 endpoint URL",
        "AWS_ACCESS_KEY_ID": "AWS access key",
        "AWS_SECRET_ACCESS_KEY": "AWS secret key",
        "VAULTWARDEN_DATA_DIR": "Vaultwarden data directory path",
        "VAULTWARDEN_DB_HOST": "PostgreSQL host",
        "VAULTWARDEN_DB_PORT": "PostgreSQL port",
        "VAULTWARDEN_DB_NAME": "PostgreSQL database name",
        "VAULTWARDEN_DB_USERNAME": "PostgreSQL username",
        "VAULTWARDEN_DB_PASSWORD": "PostgreSQL password",
    }

    for var, description in required_env_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if any(x in var.lower() for x in ['password', 'secret', 'key']):
                display_value = "***" + value[-4:] if len(value) > 4 else "****"
            else:
                display_value = value[:30] + "..." if len(value) > 30 else value
            logger.info(f"  [OK] {var:30s} - Set ({display_value})")
        else:
            logger.error(f"  [FAIL] {var:30s} - NOT SET ({description})")
            all_checks_passed = False

    # Check 3: Data directory access
    logger.info("\nChecking data directory access...")
    vw_data_dir = os.getenv("VAULTWARDEN_DATA_DIR")
    if vw_data_dir:
        data_path = Path(vw_data_dir)
        if data_path.exists() and data_path.is_dir():
            if os.access(data_path, os.R_OK):
                logger.info(f"  [OK] Vaultwarden data directory accessible: {data_path}")
            else:
                logger.error(f"  [FAIL] Vaultwarden data directory not readable: {data_path}")
                all_checks_passed = False
        else:
            logger.error(f"  [FAIL] Vaultwarden data directory not found: {data_path}")
            all_checks_passed = False

    # Check 4: Backup directory writable
    backup_dir = BACKUP_DIR
    logger.info("\nChecking backup directory...")
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        test_file = backup_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
        logger.info(f"  [OK] Backup directory writable: {backup_dir}")
    except Exception as e:
        logger.error(f"  [FAIL] Backup directory not writable: {backup_dir} ({e})")
        all_checks_passed = False

    # Check 5: Python packages
    logger.info("\nChecking Python dependencies...")
    packages = ["boto3", "cryptography"]
    for package in packages:
        try:
            __import__(package)
            logger.info(f"  [OK] {package:20s} - Installed")
        except ImportError:
            logger.error(f"  [FAIL] {package:20s} - NOT INSTALLED")
            all_checks_passed = False

    # Summary
    logger.info("\n" + "=" * 70)
    if all_checks_passed:
        logger.info("ALL DEPENDENCY CHECKS PASSED")
    else:
        logger.error("SOME DEPENDENCY CHECKS FAILED")
    logger.info("=" * 70 + "\n")

    return all_checks_passed


def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte URL-safe base64 key from the password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def upload_to_s3(file_path: Path, object_name: str):
    """Uploads the file to Cloudflare R2 (S3 Compatible)."""
    s3_client = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    logger.info(f"Uploading {object_name} to {S3_BUCKET}...")
    s3_client.upload_file(str(file_path), S3_BUCKET, object_name)
    logger.info("Upload successful.")


def list_backup_files(s3_client) -> list:
    """Lists all backup files in the S3 bucket, sorted by timestamp (oldest first)."""
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix="vaultwarden-backup-")

        if 'Contents' not in response:
            return []

        # Filter for encrypted backup files and sort by last modified date
        backup_files = [
            obj for obj in response['Contents']
            if obj['Key'].startswith('vaultwarden-backup-') and obj['Key'].endswith('.tar.gz.enc')
        ]

        # Sort by LastModified (oldest first)
        backup_files.sort(key=lambda x: x['LastModified'])

        return backup_files
    except Exception as e:
        logger.error(f"Failed to list backup files: {e}")
        return []


def delete_old_backups(s3_client):
    """Deletes old backups keeping only the latest MAX_BACKUPS_TO_KEEP versions."""
    logger.info(f"Checking for old backups (retention policy: keep last {MAX_BACKUPS_TO_KEEP})...")

    backup_files = list_backup_files(s3_client)

    if not backup_files:
        logger.info("No existing backups found in S3 bucket.")
        return

    total_backups = len(backup_files)
    logger.info(f"Found {total_backups} backup(s) in S3 bucket.")

    # Calculate how many to delete
    backups_to_delete = total_backups - MAX_BACKUPS_TO_KEEP

    if backups_to_delete <= 0:
        logger.info(f"No backups need to be deleted (current: {total_backups}, retention: {MAX_BACKUPS_TO_KEEP}).")
        return

    logger.info(f"Deleting {backups_to_delete} old backup(s)...")

    # Delete oldest backups
    for i in range(backups_to_delete):
        backup_key = backup_files[i]['Key']
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=backup_key)
            logger.info(f"Deleted old backup: {backup_key}")
        except Exception as e:
            logger.error(f"Failed to delete {backup_key}: {e}")

    logger.info(f"Retention cleanup completed. Kept {MAX_BACKUPS_TO_KEEP} most recent backup(s).")


def main() -> int:
    tar_path: Path | None = None
    encrypted_path: Path | None = None
    backup_successful = False

    try:
        # Check all dependencies first
        if not check_dependencies():
            logger.critical("Dependency checks failed. Cannot proceed with backup.")
            return 1

        logger.info("\n" + "=" * 70)
        logger.info("STARTING BACKUP PROCESS")
        logger.info("=" * 70 + "\n")

        # Phase 1: Backup database
        logger.info("PHASE 1: Backing up PostgreSQL database...")
        backup_postgres()
        logger.info("Database backup completed\n")

        # Phase 2: Backup data directory
        logger.info("PHASE 2: Backing up Vaultwarden data directory...")
        backup_vaultwarden_data()
        logger.info("Data directory backup completed\n")

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
        tar_path = SCRIPT_DIR / f"vaultwarden-backup-{timestamp}.tar.gz"
        encrypted_path = SCRIPT_DIR / f"vaultwarden-backup-{timestamp}.tar.gz.enc"

        # Phase 3: Compress
        logger.info("PHASE 3: Compressing backup archive...")
        logger.info(f"Creating: {tar_path.name}")
        with tarfile.open(tar_path, "w:gz") as tar:
            if BACKUP_SOURCE_DB.exists():
                tar.add(BACKUP_SOURCE_DB, arcname="vaultwarden.dump")
            else:
                raise FileNotFoundError(f"Database dump not found at {BACKUP_SOURCE_DB}")

            if BACKUP_SOURCE_DATA.exists():
                tar.add(BACKUP_SOURCE_DATA, arcname="data")
            else:
                raise FileNotFoundError(f"Data directory not found at {BACKUP_SOURCE_DATA}")

        tar_size_mb = tar_path.stat().st_size / (1024 * 1024)
        logger.info(f"Compression completed ({tar_size_mb:.2f} MB)\n")

        # Phase 4: Encrypt
        logger.info("PHASE 4: Encrypting backup archive...")
        salt = os.urandom(16)
        key = derive_key(BACKUP_PASSWORD, salt)
        fernet = Fernet(key)

        with open(tar_path, "rb") as f:
            encrypted_data = fernet.encrypt(f.read())

        with open(encrypted_path, "wb") as f:
            f.write(salt + encrypted_data)

        enc_size_mb = encrypted_path.stat().st_size / (1024 * 1024)
        logger.info(f"Encryption completed ({enc_size_mb:.2f} MB)\n")

        # Phase 5: Upload to S3
        logger.info("PHASE 5: Uploading to S3...")
        upload_to_s3(encrypted_path, encrypted_path.name)
        logger.info("Upload completed\n")

        # Mark backup as successful
        backup_successful = True

        # Phase 6: Cleanup old backups (only if backup was successful)
        logger.info("PHASE 6: Cleaning up old backups...")
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        delete_old_backups(s3_client)

        logger.info("\n" + "=" * 70)
        logger.info("BACKUP COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info(f"\nBackup file: {encrypted_path.name}")
        logger.info(f"Original size: {tar_size_mb:.2f} MB")
        logger.info(f"Encrypted size: {enc_size_mb:.2f} MB")
        logger.info(f"Uploaded to: {S3_BUCKET}/{encrypted_path.name}")
        logger.info(f"Timestamp: {timestamp}\n")

        return 0

    except Exception as e:
        logger.critical(f"Backup process failed: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup temporary files
        logger.info("Cleaning up local files...")
        for path in [tar_path, encrypted_path]:
            if path and path.exists():
                path.unlink()
                logger.info(f"Removed {path.name}")

if __name__ == "__main__":
    sys.exit(main())