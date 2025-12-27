import os
import tarfile
import datetime
import boto3
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from logger_config import setup_logger
from backup_db import backup_postgres
from backup_data import backup_vaultwarden_data

logger = setup_logger("backup_worker")

S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
AWS_REGION = os.getenv("AWS_REGION", "auto")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")

BACKUP_SOURCE_DB = "backup/db/vaultwarden.dump"
BACKUP_SOURCE_DATA = "backup/data/"


def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte URL-safe base64 key from the password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def upload_to_s3(file_path, object_name):
    """Uploads the file to Cloudflare R2 (S3 Compatible)."""
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        logger.info(f"Uploading {object_name} to {S3_BUCKET}...")
        s3_client.upload_file(file_path, S3_BUCKET, object_name)
        logger.info("Upload successful.")
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")
        raise e


if __name__ == "__main__":
    tar_filename = None
    encrypted_filename = None
    try:
        # 1. Execute existing backup functions
        logger.info("Starting backup process...")
        backup_postgres()
        backup_vaultwarden_data()
        # Generate timestamp for naming
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        tar_filename = f"vaultwarden-backup-{timestamp}.tar.gz"
        encrypted_filename = f"{tar_filename}.enc"

        # 2. Compress: Create a tar.gz file
        logger.info(f"Compressing data to {tar_filename}...")
        with tarfile.open(tar_filename, "w:gz") as tar:
            if os.path.exists(BACKUP_SOURCE_DB):
                tar.add(BACKUP_SOURCE_DB, arcname="vaultwarden.dump")
            else:
                logger.warning(f"Database dump not found at {BACKUP_SOURCE_DB}")

            if os.path.exists(BACKUP_SOURCE_DATA):
                tar.add(BACKUP_SOURCE_DATA, arcname="data")
            else:
                logger.warning(f"Data directory not found at {BACKUP_SOURCE_DATA}")

        # 3. Encrypt: Use Fernet (Symmetric AES)
        logger.info("Encrypting backup archive...")
        if not BACKUP_PASSWORD:
            raise ValueError("BACKUP_PASSWORD environment variable is missing!")

        salt = os.urandom(16)
        key = derive_key(BACKUP_PASSWORD, salt)
        fernet = Fernet(key)

        with open(tar_filename, "rb") as f:
            original_data = f.read()

        encrypted_data = fernet.encrypt(original_data)

        with open(encrypted_filename, "wb") as f:
            f.write(salt + encrypted_data)
        stop = 0
        # # 4. Upload to Cloudflare R2
        # upload_to_s3(encrypted_filename, encrypted_filename)

    except Exception as e:
        logger.critical(f"Backup process failed: {e}", exc_info=True)

    # finally:
    #     # 5. Cleanup temporary files
    #     logger.info("Cleaning up local files...")
    #     if tar_filename and os.path.exists(tar_filename):
    #         os.remove(tar_filename)
    #     if encrypted_filename and os.path.exists(encrypted_filename):
    #         os.remove(encrypted_filename)
    #
    #     logger.info("Backup workflow finished.")