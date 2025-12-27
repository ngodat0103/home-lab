import os
import subprocess
from pathlib import Path

DB_TYPE = os.getenv("VAULTWARDEN_DB_TYPE")
BACKUP_DIR = Path("backup/db")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def backup_sqlite():
    sqlite_path = os.getenv("VAULTWARDEN_SQLITE_PATH")
    target = BACKUP_DIR / "vaultwarden.sqlite3"
    subprocess.run(
        ["sqlite3", sqlite_path, f".backup {target}"],
        check=True,
    )

def backup_postgres():
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("VAULTWARDEN_DB_PASSWORD")

    subprocess.run(
        [
            "pg_dump",
            "-h", os.getenv("VAULTWARDEN_DB_HOST"),
            "-p", os.getenv("VAULTWARDEN_DB_PORT", "5432"),
            "-U", os.getenv("VAULTWARDEN_DB_USERNAME"),
            "-F", "c",
            "-f", str(BACKUP_DIR / "vaultwarden.dump"),
            os.getenv("VAULTWARDEN_DB_NAME"),
        ],
        env=env,
        check=True,
    )
def backup_mysql():
    subprocess.run(
        [
            "mysqldump",
            "-h", os.getenv("VAULTWARDEN_DB_HOST"),
            "-P", os.getenv("VAULTWARDEN_DB_PORT", "3306"),
            "-u", os.getenv("VAULTWARDEN_DB_USERNAME"),
            f"-p{os.getenv('VAULTWARDEN_DB_PASSWORD')}",
            os.getenv("VAULTWARDEN_DB_NAME"),
        ],
        stdout=open(BACKUP_DIR / "vaultwarden.sql", "w"),
        check=True,
    )

if DB_TYPE == "sqlite":
    backup_sqlite()
elif DB_TYPE == "postgres":
    backup_postgres()
elif DB_TYPE == "mysql":
    backup_mysql()
else:
    raise RuntimeError(f"Unsupported DB type: {DB_TYPE}")
