import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from logger_config import setup_logger

load_dotenv()

logger = setup_logger("postgres_backup")
DB_TYPE = os.getenv("VAULTWARDEN_DB_TYPE")
BACKUP_DB_DIR = Path("backup/db")
BACKUP_DB_DIR.mkdir(parents=True, exist_ok=True)

def install_postgres_client():
    logger.info("Attempting to install PostgreSQL 16 client...")
    try:
        logger.info("Running apt update...")
        subprocess.run(["apt", "update"], check=True, capture_output=True)
        logger.info("Installing postgresql-client-16...")
        subprocess.run(["apt", "install", "-y", "postgresql-client-16"], check=True, capture_output=True)
        logger.info("Installation successful.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to auto-install PostgreSQL client.")
        logger.error(f"Details: {e.stderr.decode() if e.stderr else 'Unknown error'}")
        return False

def backup_postgres():
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("VAULTWARDEN_DB_PASSWORD")

    dump_cmd = [
        "pg_dump",
        "-h", os.getenv("VAULTWARDEN_DB_HOST"),
        "-p", os.getenv("VAULTWARDEN_DB_PORT", "5432"),
        "-U", os.getenv("VAULTWARDEN_DB_USERNAME"),
        "-F", "c",
        "-f", str(BACKUP_DB_DIR / "vaultwarden.dump"),
        os.getenv("VAULTWARDEN_DB_NAME"),
    ]

    try:
        logger.info("Starting PostgreSQL backup...")
        subprocess.run(dump_cmd, env=env, check=True, capture_output=True)
        logger.info(f"Backup completed successfully at: {BACKUP_DB_DIR / 'vaultwarden.dump'}")

    except FileNotFoundError:
        logger.warning("EXECUTABLE MISSING: 'pg_dump' not found.")

        # --- AUTO-INSTALL LOGIC START ---
        logger.info("\n" + "=" * 40)
        logger.info(" ACTION REQUIRED: Installing PostgreSQL 16 Client")
        logger.info("=" * 40 + "\n")

        if install_postgres_client():
            logger.info("Retrying backup after installation...")
            try:
                # Retry the backup command
                subprocess.run(dump_cmd, env=env, check=True, capture_output=True)
                logger.info(f"Backup completed successfully at: {BACKUP_DB_DIR / 'vaultwarden.dump'}")
            except Exception as e:
                logger.error(f"Retry failed: {e}")
                sys.exit(1)
        else:
            logger.critical("Auto-installation failed. Please install manually.")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode().strip() if e.stderr else "Unknown error"
        logger.error(f"Backup failed with exit code {e.returncode}")
        logger.error(f"Details: {error_message}")
        sys.exit(e.returncode)