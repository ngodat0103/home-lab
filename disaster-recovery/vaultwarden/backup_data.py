import os
import shutil
from pathlib import Path

from logger_config import setup_logger

logger = setup_logger("backup_vaultwarden_directory")

SCRIPT_DIR = Path(__file__).parent.resolve()
BACKUP_DATA_DIR = SCRIPT_DIR / "backup" / "data"
VAULTWARDEN_DATA_DIR = os.getenv("VAULTWARDEN_DATA_DIR")


def backup_vaultwarden_data():
    logger.info("Backup started...")
    if not VAULTWARDEN_DATA_DIR:
        raise RuntimeError("VAULTWARDEN_DATA_DIR environment variable is not set")
    source_dir = Path(VAULTWARDEN_DATA_DIR)

    if not source_dir.exists() or not source_dir.is_dir():
        raise RuntimeError(f"Vaultwarden data directory not found: {source_dir}")

    # Clear old backup data to avoid stale files persisting
    if BACKUP_DATA_DIR.exists():
        logger.info(f"Clearing old backup data at {BACKUP_DATA_DIR}")
        shutil.rmtree(BACKUP_DATA_DIR)
    BACKUP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Copying data from %s to %s", source_dir, BACKUP_DATA_DIR)
    shutil.copytree(
        src=source_dir,
        dst=BACKUP_DATA_DIR,
        symlinks=True,
        dirs_exist_ok=True
    )
    logger.info("Backup completed successfully")
