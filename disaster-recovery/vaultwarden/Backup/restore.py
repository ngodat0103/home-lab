#!/usr/bin/env python3
"""
Full Vaultwarden Disaster Recovery Script

This script performs a complete recovery in two modes:

LOCAL MODE (Default):
1. Downloads and decrypts backup from S3 (or uses local file)
2. Stops running containers (vaultwarden, postgres)
3. Restores PostgreSQL database using pg_restore
4. Restores Vaultwarden data directory
5. Brings all containers back online

REMOTE MODE (--mode=remote):
1. Downloads and decrypts backup locally
2. Connects to remote VM via SSH
3. Transfers backup to remote server
4. Restores remote PostgreSQL database
5. Restores remote Vaultwarden data directory
6. Restarts remote services

Perfect for 2AM disaster recovery! Clear, actionable logging at every step.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
import base64
import docker
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

from logger_config import setup_logger

CONTAINER_START_TIMEOUT = 30
POSTGRES_READY_TIMEOUT = 60
SSH_TIMEOUT = 30

def log_section(title: str, char: str = "═"):
    """Helper to log major sections with clear visual separation."""
    logger.info("\n" + char * 70)
    logger.info(title)
    logger.info(char * 70)


def log_subsection(title: str):
    """Helper to log subsections."""
    logger.info(f"\n{'─' * 70}")
    logger.info(f"  {title}")
    logger.info(f"{'─' * 70}")


def log_hint(message: str):
    """Log a helpful hint for troubleshooting."""
    logger.info(f"💡 HINT: {message}")


def check_dependencies(mode: str = "local") -> bool:
    """Check all required dependencies before starting restore."""
    log_section("🔍 PRE-FLIGHT DEPENDENCY CHECK", "=")
    logger.info(f"Mode: {mode.upper()}")
    
    all_checks_passed = True
    
    # Check 1: Required executables
    log_subsection("Required Executables")
    
    if mode == "local":
        executables = {
            "pg_restore": "PostgreSQL restore utility",
            "psql": "PostgreSQL interactive terminal",
            "pg_isready": "PostgreSQL connection check utility",
            "docker": "Docker CLI"
        }
    else:  # remote mode
        executables = {
            "ssh": "SSH client",
            "scp": "Secure copy client (usually comes with SSH)",
        }
        # pg_restore can be local or remote - we'll check remote later
    
    for exe, description in executables.items():
        if shutil.which(exe):
            logger.info(f"  ✅ {exe:15s} - Found")
        else:
            logger.error(f"  ❌ {exe:15s} - NOT FOUND ({description})")
            if exe == "pg_restore":
                log_hint("Install with: sudo apt install postgresql-client-16")
            elif exe == "ssh":
                log_hint("Install with: sudo apt install openssh-client")
            elif exe == "docker":
                log_hint("Install from: https://docs.docker.com/engine/install/")
            all_checks_passed = False
    
    # Check 2: Required environment variables
    log_subsection("Environment Variables")
    
    required_env_vars = {
        "BACKUP_PASSWORD": "Encryption password for backup",
    }
    
    if mode == "local":
        required_env_vars.update({
            "VAULTWARDEN_DB_HOST": "PostgreSQL host",
            "VAULTWARDEN_DB_PORT": "PostgreSQL port",
            "VAULTWARDEN_DB_NAME": "PostgreSQL database name",
            "VAULTWARDEN_DB_USERNAME": "PostgreSQL username",
            "VAULTWARDEN_DB_PASSWORD": "PostgreSQL password",
        })
    else:  # remote mode
        required_env_vars.update({
            "SSH_HOST": "Remote server hostname/IP",
            "SSH_USER": "SSH username",
            "VAULTWARDEN_DB_HOST": "PostgreSQL host (from remote server's perspective)",
            "VAULTWARDEN_DB_PORT": "PostgreSQL port",
            "VAULTWARDEN_DB_NAME": "PostgreSQL database name",
            "VAULTWARDEN_DB_USERNAME": "PostgreSQL username",
            "VAULTWARDEN_DB_PASSWORD": "PostgreSQL password",
        })
        # SSH_KEY_PATH or SSH_PASSWORD required (check later)
    
    # S3 vars are optional (can use local file)
    optional_env_vars = {
        "S3_BUCKET": "S3 bucket name",
        "S3_ENDPOINT": "S3 endpoint URL",
        "AWS_ACCESS_KEY_ID": "AWS access key",
        "AWS_SECRET_ACCESS_KEY": "AWS secret key",
    }
    
    logger.info("\n  Required:")
    for var, description in required_env_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if any(x in var.lower() for x in ['password', 'secret', 'key']):
                display_value = "***" + value[-4:] if len(value) > 4 else "****"
            else:
                display_value = value[:30] + "..." if len(value) > 30 else value
            logger.info(f"    ✅ {var:30s} = {display_value}")
        else:
            logger.error(f"    ❌ {var:30s} - NOT SET ({description})")
            log_hint(f"Set {var} in your .env file or environment")
            all_checks_passed = False
    
    # Special check for SSH authentication in remote mode
    if mode == "remote":
        ssh_key = os.getenv("SSH_KEY_PATH")
        ssh_pass = os.getenv("SSH_PASSWORD")
        if ssh_key and Path(ssh_key).exists():
            logger.info(f"    ✅ {'SSH_KEY_PATH':30s} = {ssh_key}")
            logger.info(f"       (Using key-based authentication)")
        elif ssh_pass:
            logger.info(f"    ✅ {'SSH_PASSWORD':30s} = ****{ssh_pass[-4:] if len(ssh_pass) > 4 else '****'}")
            logger.info(f"       (Using password authentication)")
            logger.warning("    ⚠️  Password authentication is less secure than SSH keys!")
        else:
            logger.error(f"    ❌ SSH authentication not configured!")
            logger.error(f"       Set either SSH_KEY_PATH or SSH_PASSWORD")
            log_hint("For key: export SSH_KEY_PATH=~/.ssh/id_rsa")
            log_hint("For pass: export SSH_PASSWORD='your-ssh-password'")
            all_checks_passed = False
    
    logger.info("\n  Optional (for S3 download):")
    all_s3_set = True
    for var, description in optional_env_vars.items():
        value = os.getenv(var)
        if value:
            if any(x in var.lower() for x in ['password', 'secret', 'key']):
                display_value = "***" + value[-4:] if len(value) > 4 else "****"
            else:
                display_value = value[:30] + "..." if len(value) > 30 else value
            logger.info(f"    ✅ {var:30s} = {display_value}")
        else:
            logger.info(f"    ➖ {var:30s} - Not set")
            all_s3_set = False
    
    if not all_s3_set:
        logger.info("    ℹ️  S3 download unavailable. Ensure backup file exists locally.")
        log_hint("Provide local file path as argument to script")
    
    # Check 3: Connectivity (Docker for local, SSH for remote)
    if mode == "local":
        log_subsection("Docker Connectivity")
        try:
            client = docker.from_env()
            client.ping()
            logger.info("  ✅ Docker daemon is accessible")
            
            # Check for compose file
            if COMPOSE_FILE.exists():
                logger.info(f"  ✅ Docker Compose file found: {COMPOSE_FILE}")
            else:
                logger.warning(f"  ⚠️  Docker Compose file not found: {COMPOSE_FILE}")
                log_hint("Ensure compose.yaml exists in the script directory")
        except docker.errors.DockerException as e:
            logger.error(f"  ❌ Cannot connect to Docker daemon: {e}")
            log_hint("Check if Docker is running: sudo systemctl status docker")
            log_hint("Or try: sudo systemctl start docker")
            all_checks_passed = False
    else:  # remote mode
        log_subsection("SSH Connectivity")
        if SSH_HOST:
            logger.info(f"  Testing SSH connection to {SSH_USER}@{SSH_HOST}:{SSH_PORT}...")
            ssh_test = test_ssh_connection()
            if ssh_test:
                logger.info(f"  ✅ SSH connection successful")
            else:
                logger.error(f"  ❌ SSH connection failed")
                log_hint(f"Test manually: ssh {SSH_USER}@{SSH_HOST} -p {SSH_PORT}")
                if SSH_KEY_PATH:
                    log_hint(f"Using key: ssh -i {SSH_KEY_PATH} {SSH_USER}@{SSH_HOST}")
                all_checks_passed = False
        else:
            logger.error(f"  ❌ SSH_HOST not configured")
            all_checks_passed = False
    
    # Check 4: Restore directory writable
    log_subsection("Local Workspace")
    try:
        RESTORE_TEMP.mkdir(parents=True, exist_ok=True)
        test_file = RESTORE_TEMP / ".write_test"
        test_file.touch()
        test_file.unlink()
        logger.info(f"  ✅ Restore directory writable: {RESTORE_TEMP}")
    except Exception as e:
        logger.error(f"  ❌ Restore directory not writable: {RESTORE_TEMP}")
        logger.error(f"     Error: {e}")
        log_hint(f"Check permissions: ls -ld {RESTORE_TEMP.parent}")
        all_checks_passed = False
    
    # Check 5: Python packages
    log_subsection("Python Dependencies")
    packages = ["boto3", "cryptography"]
    if mode == "local":
        packages.append("docker")
    
    for package in packages:
        try:
            __import__(package)
            logger.info(f"  ✅ {package:20s} - Installed")
        except ImportError:
            logger.error(f"  ❌ {package:20s} - NOT INSTALLED")
            log_hint(f"Install with: pip install {package}")
            all_checks_passed = False
    
    # Summary
    logger.info("\n" + "=" * 70)
    if all_checks_passed:
        logger.info("✅ ALL PRE-FLIGHT CHECKS PASSED - Ready to proceed!")
        logger.info("=" * 70)
    else:
        logger.error("❌ SOME PRE-FLIGHT CHECKS FAILED")
        logger.error("=" * 70)
        logger.error("\n🚨 CANNOT PROCEED - Please fix the issues above")
        log_hint("Review each ❌ and follow the 💡 hints to resolve issues")
    logger.info("")
    
    return all_checks_passed


def test_ssh_connection() -> bool:
    """Test SSH connection to remote server."""
    try:
        ssh_cmd = ["ssh", "-p", SSH_PORT, "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]
        
        if SSH_KEY_PATH:
            ssh_cmd.extend(["-i", SSH_KEY_PATH])
        
        ssh_cmd.append(f"{SSH_USER}@{SSH_HOST}")
        ssh_cmd.append("echo 'SSH_CONNECTION_OK'")
        
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        return result.returncode == 0 and "SSH_CONNECTION_OK" in result.stdout
    except Exception as e:
        logger.debug(f"SSH test failed: {e}")
        return False


def run_ssh_command(command: str, timeout: int = SSH_TIMEOUT, check_output: bool = True) -> subprocess.CompletedProcess:
    """Execute command on remote server via SSH."""
    ssh_cmd = ["ssh", "-p", SSH_PORT, "-o", "ConnectTimeout=10"]
    
    if SSH_KEY_PATH:
        ssh_cmd.extend(["-i", SSH_KEY_PATH])
    
    ssh_cmd.append(f"{SSH_USER}@{SSH_HOST}")
    ssh_cmd.append(command)
    
    logger.debug(f"Executing remote command: {command}")
    
    result = subprocess.run(
        ssh_cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    if check_output and result.returncode != 0:
        logger.error(f"Remote command failed: {command}")
        logger.error(f"Exit code: {result.returncode}")
        if result.stderr:
            logger.error(f"Error output: {result.stderr}")
    
    return result


def scp_to_remote(local_path: Path, remote_path: str) -> bool:
    """Copy file to remote server using SCP."""
    try:
        scp_cmd = ["scp", "-P", SSH_PORT]
        
        if SSH_KEY_PATH:
            scp_cmd.extend(["-i", SSH_KEY_PATH])
        
        scp_cmd.extend([
            str(local_path),
            f"{SSH_USER}@{SSH_HOST}:{remote_path}"
        ])
        
        logger.info(f"  Transferring {local_path.name} to {SSH_HOST}:{remote_path}")
        logger.info(f"  File size: {local_path.stat().st_size / (1024*1024):.2f} MB")
        
        result = subprocess.run(
            scp_cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for large files
        )
        
        if result.returncode != 0:
            logger.error(f"SCP failed: {result.stderr}")
            return False
        
        logger.info(f"  ✅ Transfer complete")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("SCP timed out (file too large or connection slow)")
        log_hint("Try compressing the file more or check network connection")
        return False
    except Exception as e:
        logger.error(f"SCP failed: {e}")
        return False


class RemoteOrchestrator:
    """Manages remote server operations via SSH for disaster recovery."""
    
    def __init__(self):
        """Initialize remote orchestrator with SSH connection."""
        if not SSH_HOST:
            raise ValueError("SSH_HOST is not configured")
        
        logger.info(f"Connecting to remote server: {SSH_USER}@{SSH_HOST}:{SSH_PORT}")
        
        if not test_ssh_connection():
            raise ConnectionError(f"Cannot establish SSH connection to {SSH_HOST}")
        
        logger.info("✅ Remote server connection established")
    
    def check_remote_command(self, command: str, description: str) -> bool:
        """Check if a command exists on remote server."""
        result = run_ssh_command(f"which {command}", check_output=False)
        if result.returncode == 0:
            logger.info(f"  ✅ Remote: {command:15s} - Available")
            return True
        else:
            logger.error(f"  ❌ Remote: {command:15s} - NOT FOUND ({description})")
            log_hint(f"Install on remote: sudo apt install <package>")
            return False
    
    def create_remote_directory(self, path: str) -> bool:
        """Create directory on remote server."""
        result = run_ssh_command(f"mkdir -p {path}")
        return result.returncode == 0
    
    def stop_remote_service(self, service_name: str) -> bool:
        """Stop a systemd service on remote server."""
        if not service_name:
            logger.info("  No remote service configured, skipping stop")
            return True
        
        logger.info(f"  Stopping remote service: {service_name}")
        result = run_ssh_command(f"sudo systemctl stop {service_name}")
        
        if result.returncode != 0:
            logger.warning(f"  ⚠️  Failed to stop service (may not be running): {service_name}")
            return True  # Don't fail - service might not be running
        
        logger.info(f"  ✅ Service stopped: {service_name}")
        return True
    
    def start_remote_service(self, service_name: str) -> bool:
        """Start a systemd service on remote server."""
        if not service_name:
            logger.info("  No remote service configured, skipping start")
            return True
        
        logger.info(f"  Starting remote service: {service_name}")
        result = run_ssh_command(f"sudo systemctl start {service_name}")
        
        if result.returncode != 0:
            logger.error(f"  ❌ Failed to start service: {service_name}")
            logger.error(f"     {result.stderr}")
            log_hint(f"Check remote logs: ssh {SSH_USER}@{SSH_HOST} 'sudo journalctl -u {service_name} -n 50'")
            return False
        
        logger.info(f"  ✅ Service started: {service_name}")
        return True
    
    def check_service_status(self, service_name: str) -> Optional[str]:
        """Get status of a systemd service."""
        if not service_name:
            return None
        
        result = run_ssh_command(f"sudo systemctl is-active {service_name}", check_output=False)
        return result.stdout.strip() if result.returncode == 0 else "inactive"
    
    def wait_for_postgres_remote(self, timeout: int = POSTGRES_READY_TIMEOUT) -> bool:
        """Wait for PostgreSQL to be ready on remote server."""
        logger.info("  Waiting for remote PostgreSQL to be ready...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = run_ssh_command(
                f"PGPASSWORD='{DB_PASSWORD}' pg_isready -h {DB_HOST} -p {DB_PORT} -U {DB_USER}",
                check_output=False,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("  ✅ Remote PostgreSQL is ready")
                return True
            
            time.sleep(2)
        
        logger.error(f"  ❌ Remote PostgreSQL did not become ready within {timeout} seconds")
        log_hint(f"Check PostgreSQL on remote: ssh {SSH_USER}@{SSH_HOST} 'sudo systemctl status postgresql'")
        return False
    
    def restore_postgres_remote(self, remote_dump_path: str) -> bool:
        """Restore PostgreSQL database on remote server."""
        logger.info(f"  Restoring remote database from {remote_dump_path}...")
        
        # Drop and recreate database
        drop_cmd = f"PGPASSWORD='{DB_PASSWORD}' psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d postgres -c 'DROP DATABASE IF EXISTS {DB_NAME};'"
        create_cmd = f"PGPASSWORD='{DB_PASSWORD}' psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d postgres -c 'CREATE DATABASE {DB_NAME} OWNER {DB_USER};'"
        restore_cmd = f"PGPASSWORD='{DB_PASSWORD}' pg_restore -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d {DB_NAME} --clean --if-exists --no-owner --no-privileges {remote_dump_path}"
        
        # Drop database
        logger.info("    Dropping existing database...")
        result = run_ssh_command(drop_cmd, timeout=60, check_output=False)
        if result.returncode != 0:
            logger.warning(f"    Drop warning (database may not exist): {result.stderr[:200]}")
        
        # Create database
        logger.info("    Creating fresh database...")
        result = run_ssh_command(create_cmd, timeout=60)
        if result.returncode != 0:
            logger.error("    ❌ Failed to create database")
            return False
        
        # Restore
        logger.info("    Running pg_restore (this may take a while)...")
        result = run_ssh_command(restore_cmd, timeout=PGRESTORE_TIMEOUT, check_output=False)
        
        if result.returncode != 0:
            if "error" in result.stderr.lower():
                logger.error(f"    ❌ pg_restore failed: {result.stderr[:500]}")
                return False
            else:
                logger.warning(f"    ⚠️  pg_restore completed with warnings: {result.stderr[:200]}")
        
        logger.info("  ✅ Remote database restore successful")
        return True
    
    def restore_data_directory_remote(self, remote_extract_path: str) -> bool:
        """Restore Vaultwarden data directory on remote server."""
        remote_data_source = f"{remote_extract_path}/data"
        
        logger.info(f"  Restoring remote data directory...")
        logger.info(f"    Source: {remote_data_source}")
        logger.info(f"    Target: {REMOTE_VAULTWARDEN_DATA_DIR}")
        
        # Backup existing data directory (just in case)
        backup_cmd = f"if [ -d {REMOTE_VAULTWARDEN_DATA_DIR} ]; then sudo mv {REMOTE_VAULTWARDEN_DATA_DIR} {REMOTE_VAULTWARDEN_DATA_DIR}.backup.$(date +%s); fi"
        result = run_ssh_command(backup_cmd, check_output=False)
        
        # Create parent directory
        parent_dir = str(Path(REMOTE_VAULTWARDEN_DATA_DIR).parent)
        result = run_ssh_command(f"sudo mkdir -p {parent_dir}")
        if result.returncode != 0:
            logger.error("    ❌ Failed to create parent directory")
            return False
        
        # Copy restored data
        copy_cmd = f"sudo cp -r {remote_data_source} {REMOTE_VAULTWARDEN_DATA_DIR}"
        result = run_ssh_command(copy_cmd, timeout=300)
        if result.returncode != 0:
            logger.error("    ❌ Failed to copy data directory")
            return False
        
        logger.info("  ✅ Remote data directory restored")
        return True
    
    def cleanup_remote(self, path: str):
        """Clean up temporary files on remote server."""
        logger.info(f"  Cleaning up remote: {path}")
        run_ssh_command(f"rm -rf {path}", check_output=False)


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


def main_local(backup_filename: str) -> int:
    """
    LOCAL MODE Recovery:
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
        # Check all dependencies first
        if not check_dependencies(mode="local"):
            logger.critical("🚨 Pre-flight checks failed. Cannot proceed with restore.")
            log_hint("Fix all ❌ issues above before retrying")
            return 1

        log_section("PHASE 1: PREPARING BACKUP FILE", "═")

        if not local_encrypted_file.exists():
            logger.info(f"📥 File {local_encrypted_file} not found locally.")
            logger.info("   Attempting S3 download...")
            if not download_from_s3(backup_filename, local_encrypted_file):
                logger.error("Could not find backup file locally or in S3.")
                return 1
        else:
            file_size_mb = local_encrypted_file.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Found local backup file: {local_encrypted_file.name} ({file_size_mb:.2f} MB)")

        log_section("PHASE 2: DECRYPTING AND EXTRACTING BACKUP", "═")

        logger.info("🔓 Decrypting backup...")
        if not decrypt_backup(local_encrypted_file, decrypted_tar_file):
            return 1
        decrypted_size_mb = decrypted_tar_file.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Decryption successful ({decrypted_size_mb:.2f} MB)\n")

        logger.info("📦 Extracting archive...")
        if not extract_archive(decrypted_tar_file, RESTORE_TEMP):
            return 1
        logger.info("✅ Extraction successful\n")

        # Verify extracted contents
        logger.info("🔍 Verifying backup contents...")
        dump_file = RESTORE_TEMP / "vaultwarden.dump"
        data_dir = RESTORE_TEMP / "data"

        if not dump_file.exists():
            logger.error(f"❌ Database dump not found in backup: {dump_file}")
            return 1
        else:
            dump_size_mb = dump_file.stat().st_size / (1024 * 1024)
            logger.info(f"  ✅ Database dump found ({dump_size_mb:.2f} MB)")

        if not data_dir.exists():
            logger.error(f"❌ Data directory not found in backup: {data_dir}")
            return 1
        else:
            # Count files in data directory
            file_count = sum(1 for _ in data_dir.rglob('*') if _.is_file())
            logger.info(f"  ✅ Data directory found ({file_count} files)")

        logger.info("✅ Backup contents verified\n")

        log_section("PHASE 3: DOCKER ORCHESTRATION - STOPPING SERVICES", "═")

        docker_orchestrator = DockerOrchestrator()

        # Stop vaultwarden first (depends on postgres)
        logger.info("🛑 Stopping Vaultwarden container...")
        if not docker_orchestrator.stop_container(CONTAINER_VAULTWARDEN):
            logger.warning("⚠️  Failed to stop Vaultwarden container, continuing anyway...")
        else:
            logger.info("✅ Vaultwarden stopped\n")

        # Keep postgres running for restore, but stop vaultwarden to prevent conflicts
        # Start postgres if not running
        logger.info("🚀 Ensuring PostgreSQL container is running...")
        if not docker_orchestrator.start_container(CONTAINER_POSTGRES):
            # Try compose up to create containers if they don't exist
            logger.info("   PostgreSQL container not found, running docker compose up...")
            if not docker_orchestrator.compose_up():
                logger.error("❌ Failed to start services")
                return 1
            # Stop vaultwarden again after compose up
            docker_orchestrator.stop_container(CONTAINER_VAULTWARDEN)
        
        logger.info("✅ PostgreSQL container running\n")

        # Wait for PostgreSQL to be ready
        logger.info("⏳ Waiting for PostgreSQL to be ready...")
        if not docker_orchestrator.wait_for_postgres():
            logger.error("❌ PostgreSQL is not ready for restore")
            return 1
        logger.info("✅ PostgreSQL is ready\n")

        log_section("PHASE 4: RESTORING POSTGRESQL DATABASE", "═")

        logger.info("🗄️  Restoring database from dump...")
        if not restore_postgres_database(dump_file):
            logger.error("❌ Database restore failed!")
            return 1
        logger.info("✅ Database restore completed\n")

        log_section("PHASE 5: RESTORING VAULTWARDEN DATA", "═")

        logger.info("📁 Restoring Vaultwarden data directory...")
        if not restore_vaultwarden_data(data_dir):
            logger.error("❌ Data restore failed!")
            return 1
        logger.info("✅ Data restore completed\n")

        log_section("PHASE 6: STARTING ALL SERVICES", "═")

        logger.info("🚀 Starting all containers with docker compose...")
        if not docker_orchestrator.compose_up():
            logger.error("❌ Failed to start services")
            return 1
        logger.info("✅ Services started\n")

        # Wait a moment for services to stabilize
        logger.info("⏳ Waiting for services to stabilize...")
        time.sleep(3)

        # Verify services are running
        logger.info("🔍 Verifying container status...")
        vw_container = docker_orchestrator.get_container(CONTAINER_VAULTWARDEN)
        pg_container = docker_orchestrator.get_container(CONTAINER_POSTGRES)

        if not vw_container or vw_container.status != "running":
            logger.warning("⚠️  Vaultwarden container may not be running properly")
        else:
            logger.info(f"  ✅ {CONTAINER_VAULTWARDEN}: {vw_container.status}")

        if not pg_container or pg_container.status != "running":
            logger.warning("⚠️  PostgreSQL container may not be running properly")
        else:
            logger.info(f"  ✅ {CONTAINER_POSTGRES}: {pg_container.status}")

        log_section("✅ FULL RECOVERY COMPLETE (LOCAL MODE)", "═")
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
        logger.info("═" * 70)
        logger.info("")
        logger.info("🎉 You can go back to sleep now! Everything is restored.")
        return 0

    except KeyboardInterrupt:
        logger.warning("🛑 Recovery interrupted by user")
        return 130
    except Exception as e:
        logger.critical(f"💥 Recovery failed with unexpected error: {e}", exc_info=True)
        log_hint("Check the full error trace above for details")
        return 1
    finally:
        # Cleanup temporary files
        logger.info("\n🧹 Cleaning up temporary files...")
        cleanup_temp_files(decrypted_tar_file, RESTORE_TEMP)


def main_remote(backup_filename: str) -> int:
    """
    REMOTE MODE Recovery (for pre-provisioned infrastructure):
    1. Download/locate encrypted backup locally
    2. Decrypt and extract backup locally
    3. Connect to remote VM via SSH
    4. Transfer backup files to remote server
    5. Stop remote Vaultwarden service
    6. Restore PostgreSQL database on remote server
    7. Restore Vaultwarden data directory on remote server
    8. Start remote services
    9. Cleanup local and remote temporary files
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

    remote_orchestrator: RemoteOrchestrator | None = None

    try:
        # Check all dependencies first
        if not check_dependencies(mode="remote"):
            logger.critical("🚨 Pre-flight checks failed. Cannot proceed with restore.")
            log_hint("Fix all ❌ issues above before retrying")
            return 1

        log_section("PHASE 1: PREPARING BACKUP FILE (LOCAL)", "═")

        if not local_encrypted_file.exists():
            logger.info(f"📥 File {local_encrypted_file} not found locally.")
            logger.info("   Attempting S3 download...")
            if not download_from_s3(backup_filename, local_encrypted_file):
                logger.error("❌ Could not find backup file locally or in S3.")
                log_hint(f"Check if file exists: ls -lh {local_encrypted_file}")
                log_hint("Or verify S3 configuration in .env file")
                return 1
        else:
            file_size_mb = local_encrypted_file.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Found local backup file: {local_encrypted_file.name} ({file_size_mb:.2f} MB)")

        log_section("PHASE 2: DECRYPTING AND EXTRACTING BACKUP (LOCAL)", "═")

        logger.info("🔓 Decrypting backup...")
        if not decrypt_backup(local_encrypted_file, decrypted_tar_file):
            logger.error("❌ Decryption failed")
            log_hint("Verify BACKUP_PASSWORD is correct")
            return 1
        decrypted_size_mb = decrypted_tar_file.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Decryption successful ({decrypted_size_mb:.2f} MB)\n")

        logger.info("📦 Extracting archive...")
        if not extract_archive(decrypted_tar_file, RESTORE_TEMP):
            logger.error("❌ Extraction failed")
            return 1
        logger.info("✅ Extraction successful\n")

        # Verify extracted contents
        logger.info("🔍 Verifying backup contents...")
        dump_file = RESTORE_TEMP / "vaultwarden.dump"
        data_dir = RESTORE_TEMP / "data"

        if not dump_file.exists():
            logger.error(f"❌ Database dump not found in backup: {dump_file}")
            log_hint("Backup file may be corrupted or incomplete")
            return 1
        else:
            dump_size_mb = dump_file.stat().st_size / (1024 * 1024)
            logger.info(f"  ✅ Database dump found ({dump_size_mb:.2f} MB)")

        if not data_dir.exists():
            logger.error(f"❌ Data directory not found in backup: {data_dir}")
            return 1
        else:
            file_count = sum(1 for _ in data_dir.rglob('*') if _.is_file())
            logger.info(f"  ✅ Data directory found ({file_count} files)")

        logger.info("✅ Backup contents verified\n")

        log_section("PHASE 3: CONNECTING TO REMOTE SERVER", "═")

        logger.info(f"🔌 Establishing SSH connection to {SSH_USER}@{SSH_HOST}:{SSH_PORT}...")
        try:
            remote_orchestrator = RemoteOrchestrator()
        except (ValueError, ConnectionError) as e:
            logger.error(f"❌ Failed to connect to remote server: {e}")
            log_hint(f"Test SSH manually: ssh {SSH_USER}@{SSH_HOST} -p {SSH_PORT}")
            if SSH_KEY_PATH:
                log_hint(f"Check key permissions: chmod 600 {SSH_KEY_PATH}")
            return 1

        # Check remote dependencies
        log_subsection("Checking Remote Dependencies")
        deps_ok = True
        deps_ok &= remote_orchestrator.check_remote_command("pg_restore", "PostgreSQL client tools")
        deps_ok &= remote_orchestrator.check_remote_command("psql", "PostgreSQL client")
        deps_ok &= remote_orchestrator.check_remote_command("pg_isready", "PostgreSQL readiness check")
        
        if not deps_ok:
            logger.error("❌ Missing required tools on remote server")
            log_hint(f"Install on remote: ssh {SSH_USER}@{SSH_HOST} 'sudo apt install postgresql-client-16'")
            return 1
        
        logger.info("✅ All remote dependencies available\n")

        log_section("PHASE 4: TRANSFERRING BACKUP TO REMOTE SERVER", "═")

        # Create remote temp directory
        logger.info(f"📁 Creating remote directory: {REMOTE_TEMP_DIR}")
        if not remote_orchestrator.create_remote_directory(REMOTE_TEMP_DIR):
            logger.error("❌ Failed to create remote directory")
            return 1
        logger.info("✅ Remote directory created\n")

        # Create archive of extracted files for easier transfer
        logger.info("📦 Preparing files for transfer...")
        transfer_archive = RESTORE_TEMP.parent / "transfer.tar.gz"
        with tarfile.open(transfer_archive, "w:gz") as tar:
            tar.add(dump_file, arcname="vaultwarden.dump")
            tar.add(data_dir, arcname="data")
        logger.info(f"✅ Transfer archive created: {transfer_archive.stat().st_size / (1024*1024):.2f} MB\n")

        # Transfer to remote
        remote_transfer_path = f"{REMOTE_TEMP_DIR}/transfer.tar.gz"
        logger.info(f"📤 Transferring to remote server...")
        logger.info(f"   This may take a while depending on file size and connection speed...")
        
        if not scp_to_remote(transfer_archive, remote_transfer_path):
            logger.error("❌ Failed to transfer files to remote server")
            log_hint("Check network connection and remote disk space")
            return 1
        logger.info("✅ Transfer complete\n")

        # Extract on remote
        logger.info("📦 Extracting files on remote server...")
        extract_cmd = f"cd {REMOTE_TEMP_DIR} && tar -xzf transfer.tar.gz"
        result = run_ssh_command(extract_cmd, timeout=300)
        if result.returncode != 0:
            logger.error("❌ Failed to extract files on remote server")
            return 1
        logger.info("✅ Remote extraction complete\n")

        # Cleanup local transfer archive
        transfer_archive.unlink()

        log_section("PHASE 5: STOPPING REMOTE SERVICES", "═")

        if REMOTE_SYSTEMD_SERVICE:
            status_before = remote_orchestrator.check_service_status(REMOTE_SYSTEMD_SERVICE)
            logger.info(f"Service status before stop: {status_before}")
            
            if not remote_orchestrator.stop_remote_service(REMOTE_SYSTEMD_SERVICE):
                logger.warning("⚠️  Failed to stop service, continuing anyway...")
        else:
            logger.info("ℹ️  No REMOTE_SYSTEMD_SERVICE configured, skipping service stop")
            log_hint("Set REMOTE_SYSTEMD_SERVICE=vaultwarden.service in .env to manage service")

        log_section("PHASE 6: RESTORING REMOTE POSTGRESQL DATABASE", "═")

        # Check if PostgreSQL is accessible
        if not remote_orchestrator.wait_for_postgres_remote():
            logger.error("❌ Remote PostgreSQL is not accessible")
            log_hint(f"Check PostgreSQL on remote: ssh {SSH_USER}@{SSH_HOST} 'sudo systemctl status postgresql'")
            log_hint(f"Check connection: ssh {SSH_USER}@{SSH_HOST} 'pg_isready -h {DB_HOST} -p {DB_PORT}'")
            return 1

        remote_dump_path = f"{REMOTE_TEMP_DIR}/vaultwarden.dump"
        if not remote_orchestrator.restore_postgres_remote(remote_dump_path):
            logger.error("❌ Remote database restore failed!")
            log_hint(f"Check remote logs: ssh {SSH_USER}@{SSH_HOST} 'sudo tail -100 /var/log/postgresql/postgresql-*.log'")
            return 1
        logger.info("✅ Remote database restore completed\n")

        log_section("PHASE 7: RESTORING REMOTE VAULTWARDEN DATA", "═")

        if not remote_orchestrator.restore_data_directory_remote(REMOTE_TEMP_DIR):
            logger.error("❌ Remote data restore failed!")
            return 1
        logger.info("✅ Remote data restore completed\n")

        log_section("PHASE 8: STARTING REMOTE SERVICES", "═")

        if REMOTE_SYSTEMD_SERVICE:
            if not remote_orchestrator.start_remote_service(REMOTE_SYSTEMD_SERVICE):
                logger.error("❌ Failed to start remote service")
                log_hint(f"Check service logs: ssh {SSH_USER}@{SSH_HOST} 'sudo journalctl -u {REMOTE_SYSTEMD_SERVICE} -n 100'")
                return 1
            
            # Wait a moment for service to stabilize
            logger.info("⏳ Waiting for service to stabilize...")
            time.sleep(5)
            
            status_after = remote_orchestrator.check_service_status(REMOTE_SYSTEMD_SERVICE)
            logger.info(f"Service status after start: {status_after}")
            
            if status_after == "active":
                logger.info("✅ Remote service is running")
            else:
                logger.warning(f"⚠️  Remote service status: {status_after}")
                log_hint(f"Check logs: ssh {SSH_USER}@{SSH_HOST} 'sudo journalctl -u {REMOTE_SYSTEMD_SERVICE} -f'")
        else:
            logger.info("ℹ️  No REMOTE_SYSTEMD_SERVICE configured, skipping service start")

        log_section("✅ FULL RECOVERY COMPLETE (REMOTE MODE)", "═")
        logger.info("")
        logger.info("Remote server recovered successfully:")
        logger.info(f"  • Remote Host: {SSH_USER}@{SSH_HOST}")
        logger.info(f"  • PostgreSQL Database: {DB_NAME} on {DB_HOST}:{DB_PORT}")
        logger.info(f"  • Data Directory: {REMOTE_VAULTWARDEN_DATA_DIR}")
        if REMOTE_SYSTEMD_SERVICE:
            logger.info(f"  • Service: {REMOTE_SYSTEMD_SERVICE} ({status_after})")
        logger.info("")
        logger.info("Restored from:")
        logger.info(f"  • Backup file: {backup_file.name}")
        logger.info(f"  • Backup date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")
        logger.info("Next steps:")
        logger.info(f"  1. Verify service: ssh {SSH_USER}@{SSH_HOST} 'systemctl status {REMOTE_SYSTEMD_SERVICE or 'vaultwarden'}'")
        logger.info(f"  2. Check logs: ssh {SSH_USER}@{SSH_HOST} 'sudo journalctl -u {REMOTE_SYSTEMD_SERVICE or 'vaultwarden'} -n 50'")
        logger.info(f"  3. Test application access")
        logger.info("═" * 70)
        logger.info("")
        logger.info("🎉 You can go back to sleep now! Everything is restored.")
        return 0

    except KeyboardInterrupt:
        logger.warning("🛑 Recovery interrupted by user")
        return 130
    except Exception as e:
        logger.critical(f"💥 Recovery failed with unexpected error: {e}", exc_info=True)
        log_hint("Check the full error trace above for details")
        return 1
    finally:
        # Cleanup temporary files
        logger.info("\n🧹 Cleaning up temporary files...")
        cleanup_temp_files(decrypted_tar_file, RESTORE_TEMP)
        if remote_orchestrator:
            remote_orchestrator.cleanup_remote(REMOTE_TEMP_DIR)


def main(backup_filename: str, mode: str = "local") -> int:
    """
    Main entry point - routes to local or remote recovery mode.
    
    Args:
        backup_filename: Path to backup file
        mode: "local" for Docker-based recovery, "remote" for SSH-based recovery
    """
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 15 + "VAULTWARDEN DISASTER RECOVERY" + " " * 24 + "║")
    logger.info("║" + " " * 20 + f"Mode: {mode.upper()}" + " " * (48 - len(mode)) + "║")
    logger.info("║" + " " * 15 + datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z") + " " * 24 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")
    
    if mode == "local":
        return main_local(backup_filename)
    elif mode == "remote":
        return main_remote(backup_filename)
    else:
        logger.error(f"❌ Invalid mode: {mode}")
        logger.error("   Valid modes: 'local' or 'remote'")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Vaultwarden Disaster Recovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local Docker-based recovery (default):
  python restore.py vaultwarden-backup-2025-12-27_04-41-23_UTC.tar.gz.enc
  python restore.py /path/to/backup.tar.gz.enc
  
  # Remote SSH-based recovery (for pre-provisioned infrastructure):
  python restore.py --mode remote backup.tar.gz.enc
  python restore.py -m remote /path/to/backup.tar.gz.enc

LOCAL MODE (--mode local):
  Manages Docker containers locally:
  1. Download from S3 if file not found locally
  2. Decrypt and extract the backup
  3. Stop running containers
  4. Restore PostgreSQL database
  5. Restore Vaultwarden data directory
  6. Start all services

REMOTE MODE (--mode remote):
  Connects to remote VM via SSH:
  1. Download and decrypt backup locally
  2. Connect to remote server via SSH
  3. Transfer backup to remote
  4. Stop remote Vaultwarden service
  5. Restore remote PostgreSQL database
  6. Restore remote data directory
  7. Start remote services

Required Environment Variables (LOCAL):
  - BACKUP_PASSWORD
  - VAULTWARDEN_DB_HOST, VAULTWARDEN_DB_PORT, VAULTWARDEN_DB_NAME
  - VAULTWARDEN_DB_USERNAME, VAULTWARDEN_DB_PASSWORD

Additional Environment Variables (REMOTE):
  - SSH_HOST, SSH_PORT (default: 22), SSH_USER (default: root)
  - SSH_KEY_PATH (or SSH_PASSWORD for password auth)
  - REMOTE_VAULTWARDEN_DATA_DIR (default: /opt/vaultwarden/data)
  - REMOTE_SYSTEMD_SERVICE (optional, e.g., vaultwarden.service)
  - REMOTE_TEMP_DIR (default: /tmp/vaultwarden_restore)

Logging is designed to be clear and actionable at 2AM! 
Each step shows ✅, ❌, or ⚠️  with helpful hints 💡 when things go wrong.
        """
    )
    
    parser.add_argument(
        "backup_file",
        help="Path to encrypted backup file (.tar.gz.enc)"
    )
    
    parser.add_argument(
        "-m", "--mode",
        choices=["local", "remote"],
        default="local",
        help="Recovery mode: 'local' for Docker-based (default), 'remote' for SSH-based"
    )
    parser.add_argument(
        "--env-file",
        help="Path to env file (defaults: .env or .env.remote based on mode)"
    )
    args = parser.parse_args()

    env_file = Path(
        args.env_file or (".env.remote" if args.mode == "remote" else ".env")
    )
    load_dotenv(env_file)
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

    # Remote SSH Configuration (for --mode=remote)
    SSH_HOST = os.getenv("SSH_HOST")
    SSH_PORT = os.getenv("SSH_PORT", "22")
    SSH_USER = os.getenv("SSH_USER", "root")
    SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")
    SSH_PASSWORD = os.getenv("SSH_PASSWORD")  # Alternative to key
    # Remote paths (for --mode=remote)
    REMOTE_VAULTWARDEN_DATA_DIR = os.getenv("REMOTE_VAULTWARDEN_DATA_DIR", "/opt/vaultwarden/data")
    REMOTE_TEMP_DIR = os.getenv("REMOTE_TEMP_DIR", "/tmp/vaultwarden_restore")
    REMOTE_SYSTEMD_SERVICE = os.getenv("REMOTE_SYSTEMD_SERVICE")  # e.g., "vaultwarden.service"
    # Timeouts
    PGRESTORE_TIMEOUT = int(os.getenv("PGRESTORE_TIMEOUT", "600"))

    sys.exit(main(args.backup_file, args.mode))
