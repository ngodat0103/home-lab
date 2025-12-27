#!/usr/bin/env python3
"""
Full Vaultwarden Disaster Recovery Script

This script performs a complete recovery:
1. Downloads and decrypts backup from S3 (or uses local file)
2. Stops running containers (vaultwarden, postgres)
3. Restores PostgreSQL database using pg_restore
4. Restores Vaultwarden data directory
5. Brings all containers back online
"""
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import boto3
import base64
import docker
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

from logger_config import setup_logger

load_dotenv()

logger = setup_logger("recovery_worker")

SCRIPT_DIR = Path(__file__).parent.resolve()
COMPOSE_FILE = SCRIPT_DIR / "compose.yaml"

S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
AWS_REGION = os.getenv("AWS_REGION", "auto")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD")

DB_HOST = os.getenv("VAULTWARDEN_DB_HOST", "localhost")
DB_PORT = os.getenv("VAULTWARDEN_DB_PORT", "5432")
DB_NAME = os.getenv("VAULTWARDEN_DB_NAME", "vaultwarden")
DB_USER = os.getenv("VAULTWARDEN_DB_USERNAME", "vaultwarden")
DB_PASSWORD = os.getenv("VAULTWARDEN_DB_PASSWORD", "")

VAULTWARDEN_DATA_DIR = Path(os.getenv("VAULTWARDEN_DATA_DIR", SCRIPT_DIR / "data" / "vaultwarden"))

RESTORE_TEMP = SCRIPT_DIR / "recovery_output"

CONTAINER_VAULTWARDEN = "vaultwarden"
CONTAINER_POSTGRES = "vw-postgres"
CONTAINER_MINIO = "vw-minio"

# Timeouts
PGRESTORE_TIMEOUT = int(os.getenv("PGRESTORE_TIMEOUT", "600"))
CONTAINER_START_TIMEOUT = 30
POSTGRES_READY_TIMEOUT = 60


class DockerOrchestrator:
    """Manages Docker container lifecycle for recovery."""

    def __init__(self):
        try:
            self.client = docker.from_env()
            self.client.ping()
            logger.info("Successfully connected to Docker daemon")
        except docker.errors.DockerException as e:
            logger.critical(f"Failed to connect to Docker daemon: {e}")
            raise

    def get_container(self, name: str):
        """Get container by name, returns None if not found."""
        try:
            return self.client.containers.get(name)
        except docker.errors.NotFound:
            return None

    def stop_container(self, name: str, timeout: int = 30) -> bool:
        """Stop a container gracefully."""
        container = self.get_container(name)
        if not container:
            logger.info(f"Container '{name}' not found, skipping stop")
            return True

        if container.status != "running":
            logger.info(f"Container '{name}' is not running (status: {container.status})")
            return True

        try:
            logger.info(f"Stopping container '{name}'...")
            container.stop(timeout=timeout)
            logger.info(f"Container '{name}' stopped successfully")
            return True
        except docker.errors.APIError as e:
            logger.error(f"Failed to stop container '{name}': {e}")
            return False

    def start_container(self, name: str) -> bool:
        """Start a container."""
        container = self.get_container(name)
        if not container:
            logger.error(f"Container '{name}' not found")
            return False

        if container.status == "running":
            logger.info(f"Container '{name}' is already running")
            return True

        try:
            logger.info(f"Starting container '{name}'...")
            container.start()
            logger.info(f"Container '{name}' started successfully")
            return True
        except docker.errors.APIError as e:
            logger.error(f"Failed to start container '{name}': {e}")
            return False

    def wait_for_postgres(self, timeout: int = POSTGRES_READY_TIMEOUT) -> bool:
        """Wait for PostgreSQL to be ready to accept connections."""
        logger.info("Waiting for PostgreSQL to be ready...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                env = os.environ.copy()
                env["PGPASSWORD"] = DB_PASSWORD
                result = subprocess.run(
                    ["pg_isready", "-h", DB_HOST, "-p", DB_PORT, "-U", DB_USER],
                    env=env,
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info("PostgreSQL is ready")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            time.sleep(1)

        logger.error(f"PostgreSQL did not become ready within {timeout} seconds")
        return False

    def compose_up(self) -> bool:
        """Bring up all services using docker compose."""
        try:
            logger.info("Bringing up all services with docker compose...")
            result = subprocess.run(
                ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"],
                cwd=SCRIPT_DIR,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                logger.error(f"docker compose up failed: {result.stderr}")
                return False
            logger.info("All services started successfully")
            return True
        except subprocess.TimeoutExpired:
            logger.error("docker compose up timed out")
            return False
        except Exception as e:
            logger.error(f"Failed to run docker compose: {e}")
            return False


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
            salt = f.read(16)
            encrypted_data = f.read()

        key = derive_key(BACKUP_PASSWORD, salt)
        fernet = Fernet(key)
        decrypted_data = fernet.decrypt(encrypted_data)

        with open(output_path, "wb") as f:
            f.write(decrypted_data)

        logger.info(f"Decryption successful: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Decryption failed (Wrong password?): {e}")
        return False


def safe_extract_filter(member: tarfile.TarInfo, path: str) -> tarfile.TarInfo | None:
    """Filter for tar extraction to prevent path traversal attacks."""
    if member.name.startswith('/') or member.name.startswith('\\'):
        logger.warning(f"Skipping absolute path in archive: {member.name}")
        return None

    if '..' in member.name:
        logger.warning(f"Skipping path traversal attempt in archive: {member.name}")
        return None

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
        if extract_to.exists():
            shutil.rmtree(extract_to)
        extract_to.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tar_path, "r:gz") as tar:
            try:
                tar.extractall(path=extract_to, filter=safe_extract_filter)
            except TypeError:
                # Python < 3.12 fallback
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


def restore_postgres_database(dump_file: Path) -> bool:
    """Restore PostgreSQL database from dump file using pg_restore."""
    if not dump_file.exists():
        logger.error(f"Database dump file not found: {dump_file}")
        return False

    logger.info(f"Restoring PostgreSQL database from {dump_file}...")

    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD

    # First, drop and recreate the database to ensure clean state
    # We need to connect to 'postgres' database to drop the target database
    drop_cmd = [
        "psql",
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", "postgres",
        "-c", f"DROP DATABASE IF EXISTS {DB_NAME};"
    ]

    create_cmd = [
        "psql",
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", "postgres",
        "-c", f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};"
    ]

    restore_cmd = [
        "pg_restore",
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", DB_NAME,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        str(dump_file)
    ]

    try:
        # Drop existing database
        logger.info("Dropping existing database...")
        result = subprocess.run(drop_cmd, env=env, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            # It's okay if drop fails (database might not exist)
            logger.warning(f"Drop database warning: {result.stderr}")

        # Create fresh database
        logger.info("Creating fresh database...")
        result = subprocess.run(create_cmd, env=env, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"Failed to create database: {result.stderr}")
            return False

        # Restore from dump
        logger.info("Running pg_restore...")
        result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True, timeout=PGRESTORE_TIMEOUT)

        # pg_restore returns warnings as errors sometimes, check for actual failures
        if result.returncode != 0:
            # Check if it's just warnings
            if "error" in result.stderr.lower():
                logger.error(f"pg_restore failed: {result.stderr}")
                return False
            else:
                logger.warning(f"pg_restore completed with warnings: {result.stderr}")

        logger.info("PostgreSQL database restored successfully")
        return True

    except subprocess.TimeoutExpired:
        logger.error(f"pg_restore timed out after {PGRESTORE_TIMEOUT} seconds")
        return False
    except FileNotFoundError:
        logger.error("pg_restore not found. Please install postgresql-client-16")
        return False
    except Exception as e:
        logger.error(f"Database restore failed: {e}")
        return False


def restore_vaultwarden_data(source_dir: Path) -> bool:
    """Restore Vaultwarden data directory."""
    if not source_dir.exists():
        logger.error(f"Source data directory not found: {source_dir}")
        return False

    logger.info(f"Restoring Vaultwarden data to {VAULTWARDEN_DATA_DIR}...")

    try:
        # Ensure parent directory exists
        VAULTWARDEN_DATA_DIR.parent.mkdir(parents=True, exist_ok=True)

        # Clear existing data directory
        if VAULTWARDEN_DATA_DIR.exists():
            logger.info("Clearing existing data directory...")
            shutil.rmtree(VAULTWARDEN_DATA_DIR)

        # Copy restored data
        shutil.copytree(
            src=source_dir,
            dst=VAULTWARDEN_DATA_DIR,
            symlinks=True
        )

        logger.info("Vaultwarden data restored successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to restore Vaultwarden data: {e}")
        return False


def cleanup_temp_files(*paths: Path):
    """Clean up temporary files and directories."""
    for path in paths:
        if path and path.exists():
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                logger.info(f"Cleaned up: {path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {path}: {e}")


def main(backup_filename: str) -> int:
    """
    Steps:
    1. Download/locate encrypted backup
    2. Decrypt backup
    3. Extract archive
    4. Stop application containers
    5. Restore PostgreSQL database
    6. Restore Vaultwarden data
    7. Start all containers
    8. Cleanup
    """
    backup_file = Path(backup_filename)
    if not backup_file.is_absolute():
        backup_file = SCRIPT_DIR / backup_filename

    local_encrypted_file = backup_file
    decrypted_tar_file = (
        backup_file.with_suffix('').with_suffix('.tar.gz')
        if backup_file.suffix == '.enc'
        else backup_file.parent / backup_file.name.replace('.enc', '')
    )

    docker_orchestrator: DockerOrchestrator | None = None

    try:
        logger.info("\n" + "═" * 60)
        logger.info("PHASE 1: PREPARING BACKUP FILE")
        logger.info("═" * 60)

        if not local_encrypted_file.exists():
            logger.info(f"File {local_encrypted_file} not found locally. Attempting S3 download...")
            if not download_from_s3(backup_filename, local_encrypted_file):
                logger.error("Could not find backup file.")
                return 1

        logger.info("\n" + "═" * 60)
        logger.info("PHASE 2: DECRYPTING AND EXTRACTING BACKUP")
        logger.info("═" * 60)

        if not decrypt_backup(local_encrypted_file, decrypted_tar_file):
            return 1

        if not extract_archive(decrypted_tar_file, RESTORE_TEMP):
            return 1

        # Verify extracted contents
        dump_file = RESTORE_TEMP / "vaultwarden.dump"
        data_dir = RESTORE_TEMP / "data"

        if not dump_file.exists():
            logger.error(f"Database dump not found in backup: {dump_file}")
            return 1

        if not data_dir.exists():
            logger.error(f"Data directory not found in backup: {data_dir}")
            return 1

        logger.info("Backup contents verified")

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3: Connect to Docker and stop containers
        # ═══════════════════════════════════════════════════════════════════
        logger.info("\n" + "═" * 60)
        logger.info("PHASE 3: DOCKER ORCHESTRATION - STOPPING SERVICES")
        logger.info("═" * 60)

        docker_orchestrator = DockerOrchestrator()

        # Stop vaultwarden first (depends on postgres)
        if not docker_orchestrator.stop_container(CONTAINER_VAULTWARDEN):
            logger.warning("Failed to stop Vaultwarden container, continuing anyway...")

        # Keep postgres running for restore, but stop vaultwarden to prevent conflicts
        # Start postgres if not running
        if not docker_orchestrator.start_container(CONTAINER_POSTGRES):
            # Try compose up to create containers if they don't exist
            logger.info("PostgreSQL container not found, running docker compose up...")
            if not docker_orchestrator.compose_up():
                logger.error("Failed to start services")
                return 1
            # Stop vaultwarden again after compose up
            docker_orchestrator.stop_container(CONTAINER_VAULTWARDEN)

        # Wait for PostgreSQL to be ready
        if not docker_orchestrator.wait_for_postgres():
            logger.error("PostgreSQL is not ready for restore")
            return 1

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 4: Restore database
        # ═══════════════════════════════════════════════════════════════════
        logger.info("\n" + "═" * 60)
        logger.info("PHASE 4: RESTORING POSTGRESQL DATABASE")
        logger.info("═" * 60)

        if not restore_postgres_database(dump_file):
            logger.error("Database restore failed!")
            return 1

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 5: Restore Vaultwarden data
        # ═══════════════════════════════════════════════════════════════════
        logger.info("\n" + "═" * 60)
        logger.info("PHASE 5: RESTORING VAULTWARDEN DATA")
        logger.info("═" * 60)

        if not restore_vaultwarden_data(data_dir):
            logger.error("Data restore failed!")
            return 1

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 6: Bring services back online
        # ═══════════════════════════════════════════════════════════════════
        logger.info("\n" + "═" * 60)
        logger.info("PHASE 6: STARTING ALL SERVICES")
        logger.info("═" * 60)

        if not docker_orchestrator.compose_up():
            logger.error("Failed to start services")
            return 1

        # Wait a moment for services to stabilize
        time.sleep(3)

        # Verify services are running
        vw_container = docker_orchestrator.get_container(CONTAINER_VAULTWARDEN)
        pg_container = docker_orchestrator.get_container(CONTAINER_POSTGRES)

        if not vw_container or vw_container.status != "running":
            logger.warning("Vaultwarden container may not be running properly")

        if not pg_container or pg_container.status != "running":
            logger.warning("PostgreSQL container may not be running properly")

        logger.info("\n" + "═" * 60)
        logger.info("✅ FULL RECOVERY COMPLETE")
        logger.info("═" * 60)
        logger.info("")
        logger.info("Services restored and running:")
        logger.info(f"  • PostgreSQL: {CONTAINER_POSTGRES}")
        logger.info(f"  • Vaultwarden: {CONTAINER_VAULTWARDEN}")
        logger.info(f"  • MinIO: {CONTAINER_MINIO}")
        logger.info("")
        logger.info("Restored from:")
        logger.info(f"  • Backup file: {backup_file.name}")
        logger.info(f"  • Database: {DB_NAME}")
        logger.info(f"  • Data directory: {VAULTWARDEN_DATA_DIR}")
        logger.info("")
        logger.info("Vaultwarden should now be accessible at: http://localhost:8080")
        logger.info("═" * 60)
        return 0

    except KeyboardInterrupt:
        logger.warning("Recovery interrupted by user")
        return 130
    except Exception as e:
        logger.critical(f"Recovery failed with unexpected error: {e}", exc_info=True)
        return 1
    finally:
        # Cleanup temporary files
        logger.info("\nCleaning up temporary files...")
        cleanup_temp_files(decrypted_tar_file, RESTORE_TEMP)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python restore.py <backup_filename>")
        print("")
        print("Examples:")
        print("  python restore.py vaultwarden-backup-2025-12-27_04-41-23_UTC.tar.gz.enc")
        print("  python restore.py /path/to/backup.tar.gz.enc")
        print("")
        print("The script will:")
        print("  1. Download from S3 if file not found locally")
        print("  2. Decrypt and extract the backup")
        print("  3. Stop running containers")
        print("  4. Restore PostgreSQL database")
        print("  5. Restore Vaultwarden data directory")
        print("  6. Start all services")
        sys.exit(1)

    target_file = sys.argv[1]
    sys.exit(main(target_file))
