import os
import sys
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from logger_config import setup_logger

load_dotenv()

logger = setup_logger("postgres_backup")

# Use absolute paths based on script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKUP_DB_DIR = SCRIPT_DIR / "backup" / "db"

DB_TYPE = os.getenv("VAULTWARDEN_DB_TYPE")

# Timeout for pg_dump in seconds (5 minutes should be plenty for most databases)
PGDUMP_TIMEOUT = int(os.getenv("PGDUMP_TIMEOUT", "300"))


def install_postgres_client():
    logger.info("Attempting to install PostgreSQL 16 client...")
    try:
        logger.info("Running apt update...")
        subprocess.run(["apt", "update"], check=True, capture_output=True, timeout=120)
        logger.info("Installing postgresql-client-16...")
        subprocess.run(["apt", "install", "-y", "postgresql-client-16"], check=True, capture_output=True, timeout=300)
        logger.info("Installation successful.")
        return True
    except subprocess.TimeoutExpired:
        logger.error("Package installation timed out.")
        return False
    except subprocess.CalledProcessError as e:
        logger.error("Failed to auto-install PostgreSQL client.")
        logger.error(f"Details: {e.stderr.decode() if e.stderr else 'Unknown error'}")
        return False


def backup_postgres():
    BACKUP_DB_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("VAULTWARDEN_DB_PASSWORD", "")

    dump_file = BACKUP_DB_DIR / "vaultwarden.dump"
    dump_cmd = [
        "pg_dump",
        "-h", os.getenv("VAULTWARDEN_DB_HOST", ""),
        "-p", os.getenv("VAULTWARDEN_DB_PORT", "5432"),
        "-U", os.getenv("VAULTWARDEN_DB_USERNAME", ""),
        "-F", "c",
        "-f", str(dump_file),
        os.getenv("VAULTWARDEN_DB_NAME", ""),
    ]

    try:
        logger.info("Starting PostgreSQL backup...")
        subprocess.run(dump_cmd, env=env, check=True, capture_output=True, timeout=PGDUMP_TIMEOUT)
        logger.info(f"Backup completed successfully at: {dump_file}")

    except subprocess.TimeoutExpired:
        logger.error(f"pg_dump timed out after {PGDUMP_TIMEOUT} seconds")
        sys.exit(1)

    except FileNotFoundError:
        logger.warning("EXECUTABLE MISSING: 'pg_dump' not found.")

        # --- AUTO-INSTALL LOGIC START ---
        logger.info("\n" + "=" * 40)
        logger.info(" ACTION REQUIRED: Installing PostgreSQL 16 Client")
        logger.info("=" * 40 + "\n")

        if install_postgres_client():
            logger.info("Retrying backup after installation...")
            try:
                subprocess.run(dump_cmd, env=env, check=True, capture_output=True, timeout=PGDUMP_TIMEOUT)
                logger.info(f"Backup completed successfully at: {dump_file}")
            except subprocess.TimeoutExpired:
                logger.error(f"pg_dump timed out after {PGDUMP_TIMEOUT} seconds")
                sys.exit(1)
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
