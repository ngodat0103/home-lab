# Vaultwarden Backup & Restore Scripts

Docker container for automated backup and restore operations for Vaultwarden with PostgreSQL.

## Features

- 🔒 **Encrypted Backups**: AES encryption using PBKDF2 key derivation
- ☁️ **S3 Storage**: Upload to any S3-compatible storage (AWS S3, Cloudflare R2, MinIO)
- 🗃️ **PostgreSQL Support**: Full database dump and restore with PostgreSQL 16
- 📁 **Data Directory Backup**: Complete Vaultwarden data directory preservation
- 🐳 **Docker Integration**: Manages container lifecycle during restore
- 📝 **Comprehensive Logging**: Colored output with detailed operation tracking
- ✅ **Pre-flight Checks**: Validates all dependencies before execution
- 📊 **Progress Indicators**: Real-time status updates for each phase

## Quick Start

### Pull from GitHub Container Registry

```bash
docker pull ghcr.io/ngodat0103/homelab:vaultwarden-script
```

### Running Backup

```bash
docker run --rm \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/backup:/app/backup \
  -e VAULTWARDEN_DB_HOST=localhost \
  -e VAULTWARDEN_DB_PORT=5432 \
  -e VAULTWARDEN_DB_NAME=vaultwarden \
  -e VAULTWARDEN_DB_USERNAME=vaultwarden \
  -e VAULTWARDEN_DB_PASSWORD=yourpassword \
  -e VAULTWARDEN_DATA_DIR=/app/data/vaultwarden \
  -e S3_BUCKET=your-bucket \
  -e S3_ENDPOINT=https://your-s3-endpoint.com \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -e AWS_REGION=auto \
  -e BACKUP_PASSWORD=your-encryption-password \
  ghcr.io/ngodat0103/homelab:vaultwarden-script \
  python backup.py
```

### Running Restore

```bash
docker run --rm \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/backup:/app/backup \
  -e VAULTWARDEN_DB_HOST=localhost \
  -e VAULTWARDEN_DB_PORT=5432 \
  -e VAULTWARDEN_DB_NAME=vaultwarden \
  -e VAULTWARDEN_DB_USERNAME=vaultwarden \
  -e VAULTWARDEN_DB_PASSWORD=yourpassword \
  -e VAULTWARDEN_DATA_DIR=/app/data/vaultwarden \
  -e S3_BUCKET=your-bucket \
  -e S3_ENDPOINT=https://your-s3-endpoint.com \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -e AWS_REGION=auto \
  -e BACKUP_PASSWORD=your-encryption-password \
  ghcr.io/ngodat0103/homelab:vaultwarden-script \
  python restore.py vaultwarden-backup-2025-12-27_04-41-23_UTC.tar.gz.enc
```

## Environment Variables

### Database Configuration
- `VAULTWARDEN_DB_HOST`: PostgreSQL host (default: localhost)
- `VAULTWARDEN_DB_PORT`: PostgreSQL port (default: 5432)
- `VAULTWARDEN_DB_NAME`: Database name
- `VAULTWARDEN_DB_USERNAME`: Database user
- `VAULTWARDEN_DB_PASSWORD`: Database password
- `VAULTWARDEN_DATA_DIR`: Path to Vaultwarden data directory

### S3 Configuration
- `S3_BUCKET`: S3 bucket name
- `S3_ENDPOINT`: S3 endpoint URL
- `AWS_ACCESS_KEY_ID`: AWS/S3 access key
- `AWS_SECRET_ACCESS_KEY`: AWS/S3 secret key
- `AWS_REGION`: AWS region (default: auto)

### Backup Configuration
- `BACKUP_PASSWORD`: Password for encrypting/decrypting backups (required)
- `PGDUMP_TIMEOUT`: Timeout for pg_dump in seconds (default: 300)
- `PGRESTORE_TIMEOUT`: Timeout for pg_restore in seconds (default: 600)

## Building Locally

```bash
docker build -t vaultwarden-backup .
```

## Docker Compose Integration

Add to your `docker-compose.yml`:

```yaml
services:
  backup:
    image: ghcr.io/ngodat0103/homelab:vaultwarden-script
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data:/app/data
      - ./backup:/app/backup
    environment:
      VAULTWARDEN_DB_HOST: postgres
      VAULTWARDEN_DB_PORT: 5432
      VAULTWARDEN_DB_NAME: vaultwarden
      VAULTWARDEN_DB_USERNAME: vaultwarden
      VAULTWARDEN_DB_PASSWORD: ${VAULTWARDEN_DB_PASSWORD}
      VAULTWARDEN_DATA_DIR: /app/data/vaultwarden
      S3_BUCKET: ${S3_BUCKET}
      S3_ENDPOINT: ${S3_ENDPOINT}
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      BACKUP_PASSWORD: ${BACKUP_PASSWORD}
    command: python backup.py
    profiles:
      - backup
```

Run backup with:
```bash
docker-compose --profile backup run --rm backup
```

## Automation with Cron

Create a cron job for automated backups:

```bash
# Daily backup at 2 AM
0 2 * * * docker run --rm --network host -v /var/run/docker.sock:/var/run/docker.sock -v /path/to/data:/app/data --env-file /path/to/.env ghcr.io/ngodat0103/homelab:vaultwarden-script python backup.py
```

## Security Notes

- Store sensitive environment variables in `.env` file (never commit to git)
- Use strong `BACKUP_PASSWORD` (backups are encrypted with AES via PBKDF2)
- Restrict access to Docker socket
- Use read-only volumes where possible
- Regularly rotate S3 credentials

## Backup Process

The backup script now includes comprehensive pre-flight checks and status updates:

### Dependency Check Phase
- ✅ Validates required executables (`pg_dump`)
- ✅ Checks all required environment variables (with masked sensitive values)
- ✅ Verifies data directory accessibility
- ✅ Tests backup directory write permissions
- ✅ Confirms Python dependencies are installed

### Backup Phases
1. **Phase 1**: Dumps PostgreSQL database using `pg_dump` (custom format)
2. **Phase 2**: Copies Vaultwarden data directory
3. **Phase 3**: Creates tar.gz archive containing both (shows size)
4. **Phase 4**: Encrypts archive with password-derived key (PBKDF2 + AES, shows size)
5. **Phase 5**: Uploads encrypted backup to S3
6. **Cleanup**: Removes temporary files

Each phase provides real-time progress updates with emojis and status indicators.

## Restore Process

The restore script includes enhanced dependency checks and detailed progress tracking:

### Dependency Check Phase
- ✅ Validates required executables (`pg_restore`, `psql`, `pg_isready`, `docker`)
- ✅ Checks required environment variables (with masked sensitive values)
- ✅ Verifies optional S3 configuration (for remote downloads)
- ✅ Tests Docker daemon connectivity
- ✅ Checks restore directory write permissions
- ✅ Confirms Python dependencies are installed

### Restore Phases
1. **Phase 1**: Downloads encrypted backup from S3 (or uses local file, shows size)
2. **Phase 2**: Decrypts backup using password and extracts contents (shows sizes)
3. **Phase 3**: Stops Vaultwarden container and ensures PostgreSQL is ready
4. **Phase 4**: Restores PostgreSQL database (drops/recreates database)
5. **Phase 5**: Restores Vaultwarden data directory
6. **Phase 6**: Starts all containers via docker compose and verifies status
7. **Cleanup**: Removes temporary files

Each phase provides detailed status updates with progress indicators and container health checks.

## License

MIT

## Container Image

- **Registry**: ghcr.io/ngodat0103/homelab:vaultwarden-script
- **Base**: python:3.12-slim (optimized for minimal size)
- **Size**: ~200-300MB (reduced from 1.2GB)
- **PostgreSQL Client**: 16
- **Package Manager**: uv (for faster installs)

### Image Optimizations
- Uses slim Python base image instead of full Debian
- Single-layer APT operations with aggressive cleanup
- Removes build tools after PostgreSQL client installation
- Clears APT cache and temporary files
- Only includes runtime dependencies

