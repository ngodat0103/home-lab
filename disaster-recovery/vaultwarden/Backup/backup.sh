#!/bin/bash

set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_usage() {
    echo "Usage: $0 [ENV_FILE]"
    echo ""
    echo "Arguments:"
    echo "  ENV_FILE    Path to .env file (default: .env in current directory)"
    echo ""
    echo "Examples:"
    echo "  $0                           # Use .env in current directory"
    echo "  $0 /etc/vaultwarden/.env     # Use specific .env file"
    echo "  $0 ~/.vaultwarden_backup.env # Use .env in home directory"
}

# Parse arguments
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    print_usage
    exit 0
fi

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    print_error ".env file not found: $ENV_FILE"
    exit 1
fi

print_info "Using .env file: $ENV_FILE"
print_info "Starting Vaultwarden backup..."

# Extract LOCAL_VAULTWARDEN_DATA_DIR from .env file
LOCAL_VAULTWARDEN_DATA_DIR=$(grep -E "^LOCAL_VAULTWARDEN_DATA_DIR=" "$ENV_FILE" | cut -d '=' -f 2- | sed 's/^["'\'']//' | sed 's/["'\'']$//')

# Use default if not found in .env
if [ -z "$LOCAL_VAULTWARDEN_DATA_DIR" ]; then
    print_error "LOCAL_VAULTWARDEN_DATA_DIR not found in $ENV_FILE"
    print_info "Using default: /var/backups/vaultwarden/data"
    LOCAL_VAULTWARDEN_DATA_DIR="/var/backups/vaultwarden/data"
fi

print_info "Data directory: $LOCAL_VAULTWARDEN_DATA_DIR"

# Create directory if it doesn't exist
mkdir -p "$LOCAL_VAULTWARDEN_DATA_DIR"

# Run backup
docker run --rm \
  --network host \
  --env-file "$ENV_FILE" \
  -v "${LOCAL_VAULTWARDEN_DATA_DIR}/:/app/data/vaultwarden/:ro" \
  ghcr.io/ngodat0103/homelab/vaultwarden-backup-utility:v1 \
  python backup.py

if [ $? -eq 0 ]; then
    print_info "Backup completed successfully!"
else
    print_error "Backup failed!"
    exit 1
fi