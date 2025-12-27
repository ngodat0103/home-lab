#!/usr/bin/env python3
import os
import sys
import tarfile
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

BACKUP_SOURCE_DB = BACKUP_DIR / "db" / "vaultwarden.dump"
BACKUP_SOURCE_DATA = BACKUP_DIR / "data"


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
def main() -> int:
    tar_path: Path | None = None
    encrypted_path: Path | None = None
    try:
        # Validate required env vars upfront
        if not BACKUP_PASSWORD:
            raise ValueError("BACKUP_PASSWORD environment variable is missing!")
        if not all([S3_BUCKET, S3_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]):
            raise ValueError("S3 configuration incomplete (check S3_BUCKET, S3_ENDPOINT, AWS credentials)")

        logger.info("Starting backup process...")
        backup_postgres()
        backup_vaultwarden_data()

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
        tar_path = SCRIPT_DIR / f"vaultwarden-backup-{timestamp}.tar.gz"
        encrypted_path = SCRIPT_DIR / f"vaultwarden-backup-{timestamp}.tar.gz.enc"

        # Compress
        logger.info(f"Compressing data to {tar_path.name}...")
        with tarfile.open(tar_path, "w:gz") as tar:
            if BACKUP_SOURCE_DB.exists():
                tar.add(BACKUP_SOURCE_DB, arcname="vaultwarden.dump")
            else:
                raise FileNotFoundError(f"Database dump not found at {BACKUP_SOURCE_DB}")

            if BACKUP_SOURCE_DATA.exists():
                tar.add(BACKUP_SOURCE_DATA, arcname="data")
            else:
                raise FileNotFoundError(f"Data directory not found at {BACKUP_SOURCE_DATA}")

        logger.info("Encrypting backup archive...")
        salt = os.urandom(16)
        key = derive_key(BACKUP_PASSWORD, salt)
        fernet = Fernet(key)

        with open(tar_path, "rb") as f:
            encrypted_data = fernet.encrypt(f.read())

        with open(encrypted_path, "wb") as f:
            f.write(salt + encrypted_data)

        # Upload to S3, Temporary for quick test recovery local first
        # upload_to_s3(encrypted_path, encrypted_path.name)

        logger.info("Backup completed successfully!")
        return 0

    except Exception as e:
        logger.critical(f"Backup process failed: {e}", exc_info=True)
        return 1

        # Upload to S3, Temporary for quick test recovery local first
    # finally:
    #     # Cleanup temporary files
    #     logger.info("Cleaning up local files...")
    #     for path in [tar_path, encrypted_path]:
    #         if path and path.exists():
    #             path.unlink()
    #             logger.info(f"Removed {path.name}")


if __name__ == "__main__":
    sys.exit(main())
