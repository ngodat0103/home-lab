#!/bin/bash

set -e

# Default config file path
CONFIG_FILE="$HOME/.vaultwarden_backup.conf"
CONFIG_DIR="$HOME/.config/vaultwarden"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for non-interactive mode and config file path
NON_INTERACTIVE=false
CUSTOM_CONFIG=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config|-c)
            CONFIG_FILE="$2"
            CUSTOM_CONFIG=true
            shift 2
            ;;
        --no-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --reconfigure|--show-config|--help|-h)
            # Handle these later
            break
            ;;
        *)
            shift
            ;;
    esac
done

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to mask sensitive values
mask_value() {
    local value="$1"
    local show_chars="${2:-4}"

    if [ -z "$value" ]; then
        echo ""
        return
    fi

    local length=${#value}
    if [ $length -le $show_chars ]; then
        echo "****"
    else
        echo "${value:0:$show_chars}$(printf '*%.0s' $(seq 1 $((length - show_chars))))"
    fi
}

prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local is_secret="${4:-false}"

    if [ -n "$default" ]; then
        prompt="$prompt [$default]"
    fi

    if [ "$is_secret" = "true" ]; then
        read -sp "$prompt: " input
        echo
    else
        read -p "$prompt: " input
    fi

    if [ -z "$input" ] && [ -n "$default" ]; then
        eval "$var_name='$default'"
    else
        eval "$var_name='$input'"
    fi
}

# Function to load existing config
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        # Only print info in interactive mode
        if [ "$NON_INTERACTIVE" = false ]; then
            print_info "Found existing configuration at $CONFIG_FILE"
        fi

        source "$CONFIG_FILE"

        # Display loaded config only in interactive mode
        if [ "$NON_INTERACTIVE" = false ]; then
            echo ""
            print_info "Loaded configuration:"
            echo "  Database Host: $VAULTWARDEN_DB_HOST"
            echo "  Database Port: $VAULTWARDEN_DB_PORT"
            echo "  Database Name: $VAULTWARDEN_DB_NAME"
            echo "  Database Username: $VAULTWARDEN_DB_USERNAME"
            echo "  Database Password: $(mask_value "$VAULTWARDEN_DB_PASSWORD")"
            echo "  Data Directory: $VAULTWARDEN_DATA_DIR"
            echo "  S3 Bucket: $S3_BUCKET"
            echo "  S3 Endpoint: $S3_ENDPOINT"
            echo "  AWS Access Key: $(mask_value "$AWS_ACCESS_KEY_ID")"
            echo "  AWS Secret Key: $(mask_value "$AWS_SECRET_ACCESS_KEY")"
            echo "  AWS Region: $AWS_REGION"
            echo "  Backup Password: $(mask_value "$BACKUP_PASSWORD")"
            echo "  Local Data Dir: $LOCAL_DATA_DIR"
            echo "  Local Backup Dir: $LOCAL_BACKUP_DIR"
            echo ""
        fi

        return 0
    fi
    return 1
}

# Function to save config
save_config() {
    # Create directory for config file if needed
    local config_dir=$(dirname "$CONFIG_FILE")
    mkdir -p "$config_dir"

    cat > "$CONFIG_FILE" << EOF
# Vaultwarden Backup Configuration
# Generated on $(date)

# Database Configuration
VAULTWARDEN_DB_HOST="$VAULTWARDEN_DB_HOST"
VAULTWARDEN_DB_PORT="$VAULTWARDEN_DB_PORT"
VAULTWARDEN_DB_NAME="$VAULTWARDEN_DB_NAME"
VAULTWARDEN_DB_USERNAME="$VAULTWARDEN_DB_USERNAME"
VAULTWARDEN_DB_PASSWORD="$VAULTWARDEN_DB_PASSWORD"

# Data Directory
VAULTWARDEN_DATA_DIR="$VAULTWARDEN_DATA_DIR"

# S3 Configuration
S3_BUCKET="$S3_BUCKET"
S3_ENDPOINT="$S3_ENDPOINT"
AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
AWS_REGION="$AWS_REGION"

# Backup Configuration
BACKUP_PASSWORD="$BACKUP_PASSWORD"
LOCAL_DATA_DIR="$LOCAL_DATA_DIR"
LOCAL_BACKUP_DIR="$LOCAL_BACKUP_DIR"
EOF

    chmod 600 "$CONFIG_FILE"
    print_info "Configuration saved to $CONFIG_FILE"
}

# Function to collect configuration
collect_config() {
    echo ""
    print_info "=== Database Configuration ==="
    prompt_input "Database host" "${VAULTWARDEN_DB_HOST:-localhost}" VAULTWARDEN_DB_HOST
    prompt_input "Database port" "${VAULTWARDEN_DB_PORT:-5432}" VAULTWARDEN_DB_PORT
    prompt_input "Database name" "${VAULTWARDEN_DB_NAME:-vaultwarden}" VAULTWARDEN_DB_NAME
    prompt_input "Database username" "${VAULTWARDEN_DB_USERNAME:-vaultwarden}" VAULTWARDEN_DB_USERNAME
    prompt_input "Database password" "$(mask_value "$VAULTWARDEN_DB_PASSWORD")" VAULTWARDEN_DB_PASSWORD true

    echo ""
    print_info "=== Data Directory Configuration ==="
    prompt_input "Vaultwarden data directory" "${VAULTWARDEN_DATA_DIR:-/app/data/vaultwarden}" VAULTWARDEN_DATA_DIR

    echo ""
    print_info "=== S3 Configuration ==="
    prompt_input "S3 bucket name" "$S3_BUCKET" S3_BUCKET
    prompt_input "S3 endpoint URL" "$S3_ENDPOINT" S3_ENDPOINT
    prompt_input "AWS access key ID" "$(mask_value "$AWS_ACCESS_KEY_ID")" AWS_ACCESS_KEY_ID
    prompt_input "AWS secret access key" "$(mask_value "$AWS_SECRET_ACCESS_KEY")" AWS_SECRET_ACCESS_KEY true
    prompt_input "AWS region" "${AWS_REGION:-auto}" AWS_REGION

    echo ""
    print_info "=== Backup Configuration ==="
    prompt_input "Backup encryption password" "$(mask_value "$BACKUP_PASSWORD")" BACKUP_PASSWORD true

    # Use absolute paths for defaults
    local default_data_dir="/var/backups/vaultwarden/data"
    local default_backup_dir="/var/backups/vaultwarden/temp"

    prompt_input "Local data directory" "${LOCAL_DATA_DIR:-$default_data_dir}" LOCAL_DATA_DIR
    prompt_input "Temporary working directory" "${LOCAL_BACKUP_DIR:-$default_backup_dir}" LOCAL_BACKUP_DIR
}

# Function to validate configuration
validate_config() {
    local errors=0

    [ -z "$VAULTWARDEN_DB_HOST" ] && print_error "Database host is required" && ((errors++))
    [ -z "$VAULTWARDEN_DB_PASSWORD" ] && print_error "Database password is required" && ((errors++))
    [ -z "$S3_BUCKET" ] && print_error "S3 bucket is required" && ((errors++))
    [ -z "$S3_ENDPOINT" ] && print_error "S3 endpoint is required" && ((errors++))
    [ -z "$AWS_ACCESS_KEY_ID" ] && print_error "AWS access key ID is required" && ((errors++))
    [ -z "$AWS_SECRET_ACCESS_KEY" ] && print_error "AWS secret access key is required" && ((errors++))
    [ -z "$BACKUP_PASSWORD" ] && print_error "Backup encryption password is required" && ((errors++))

    if [ $errors -gt 0 ]; then
        print_error "Configuration validation failed with $errors error(s)"
        return 1
    fi

    if [ "$NON_INTERACTIVE" = false ]; then
        print_info "Configuration validation passed"
    fi
    return 0
}

# Function to run backup
run_backup() {
    if [ "$NON_INTERACTIVE" = false ]; then
        print_info "Starting Vaultwarden backup..."
    fi

    # Create local directories if they don't exist
    mkdir -p "$LOCAL_DATA_DIR"
    mkdir -p "$LOCAL_BACKUP_DIR"

    docker run --rm \
      --network host \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "$LOCAL_DATA_DIR:$VAULTWARDEN_DATA_DIR" \
      -v "$LOCAL_BACKUP_DIR:/app/backup" \
      -e VAULTWARDEN_DB_HOST="$VAULTWARDEN_DB_HOST" \
      -e VAULTWARDEN_DB_PORT="$VAULTWARDEN_DB_PORT" \
      -e VAULTWARDEN_DB_NAME="$VAULTWARDEN_DB_NAME" \
      -e VAULTWARDEN_DB_USERNAME="$VAULTWARDEN_DB_USERNAME" \
      -e VAULTWARDEN_DB_PASSWORD="$VAULTWARDEN_DB_PASSWORD" \
      -e VAULTWARDEN_DATA_DIR="$VAULTWARDEN_DATA_DIR" \
      -e S3_BUCKET="$S3_BUCKET" \
      -e S3_ENDPOINT="$S3_ENDPOINT" \
      -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
      -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
      -e AWS_REGION="$AWS_REGION" \
      -e BACKUP_PASSWORD="$BACKUP_PASSWORD" \
      ghcr.io/ngodat0103/homelab/vaultwarden-backup-utility:v1 \
      python backup.py

    if [ $? -eq 0 ]; then
        print_info "Backup completed successfully!"
    else
        print_error "Backup failed!"
        exit 1
    fi
}

# Main script logic
main() {
    if [ "$NON_INTERACTIVE" = false ]; then
        echo ""
        print_info "Vaultwarden Backup Script"
        echo ""
    fi

    # Try to load existing config
    if load_config; then
        # Config exists - validate and run
        if [ "$NON_INTERACTIVE" = true ]; then
            if validate_config; then
                run_backup
            else
                print_error "Configuration validation failed. Config file: $CONFIG_FILE"
                exit 1
            fi
        else
            # Interactive mode with existing config
            read -p "Do you want to use the existing configuration? (y/n) [y]: " use_existing
            use_existing=${use_existing:-y}

            if [[ ! "$use_existing" =~ ^[Yy]$ ]]; then
                print_info "Reconfiguring..."
                collect_config

                read -p "Save this configuration? (y/n) [y]: " save_conf
                save_conf=${save_conf:-y}
                [[ "$save_conf" =~ ^[Yy]$ ]] && save_config
            fi

            echo ""
            if validate_config; then
                echo ""
                read -p "Proceed with backup? (y/n) [y]: " proceed
                proceed=${proceed:-y}

                if [[ "$proceed" =~ ^[Yy]$ ]]; then
                    run_backup
                else
                    print_info "Backup cancelled"
                    exit 0
                fi
            else
                exit 1
            fi
        fi
    else
        # No config found
        if [ "$NON_INTERACTIVE" = true ]; then
            print_error "No configuration found at: $CONFIG_FILE"
            print_error "Please create a configuration file or run without --no-interactive"
            exit 1
        else
            print_warn "No existing configuration found. Please provide configuration details."
            collect_config

            read -p "Save this configuration for future use? (y/n) [y]: " save_conf
            save_conf=${save_conf:-y}
            [[ "$save_conf" =~ ^[Yy]$ ]] && save_config

            echo ""
            if validate_config; then
                echo ""
                read -p "Proceed with backup? (y/n) [y]: " proceed
                proceed=${proceed:-y}

                if [[ "$proceed" =~ ^[Yy]$ ]]; then
                    run_backup
                else
                    print_info "Backup cancelled"
                    exit 0
                fi
            else
                exit 1
            fi
        fi
    fi
}

# Handle command line arguments
case "${1:-}" in
    --reconfigure)
        load_config 2>/dev/null || true
        collect_config
        save_config
        exit 0
        ;;
    --show-config)
        if [ -f "$CONFIG_FILE" ]; then
            source "$CONFIG_FILE"
            print_info "Current configuration (from $CONFIG_FILE):"
            echo "  Database Host: $VAULTWARDEN_DB_HOST"
            echo "  Database Port: $VAULTWARDEN_DB_PORT"
            echo "  Database Name: $VAULTWARDEN_DB_NAME"
            echo "  Database Username: $VAULTWARDEN_DB_USERNAME"
            echo "  Database Password: $(mask_value "$VAULTWARDEN_DB_PASSWORD")"
            echo "  Data Directory: $VAULTWARDEN_DATA_DIR"
            echo "  S3 Bucket: $S3_BUCKET"
            echo "  S3 Endpoint: $S3_ENDPOINT"
            echo "  AWS Access Key: $(mask_value "$AWS_ACCESS_KEY_ID")"
            echo "  AWS Secret Key: $(mask_value "$AWS_SECRET_ACCESS_KEY")"
            echo "  AWS Region: $AWS_REGION"
            echo "  Backup Password: $(mask_value "$BACKUP_PASSWORD")"
            echo "  Local Data Dir: $LOCAL_DATA_DIR"
            echo "  Local Backup Dir: $LOCAL_BACKUP_DIR"
        else
            print_error "No configuration file found at $CONFIG_FILE"
            exit 1
        fi
        exit 0
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  (no args)             Run backup with interactive configuration"
        echo "  --config, -c PATH     Use custom config file path (default: ~/.vaultwarden_backup.conf)"
        echo "  --no-interactive      Run backup without prompts (requires existing config)"
        echo "  --reconfigure         Reconfigure and save settings"
        echo "  --show-config         Display current configuration (with masked passwords)"
        echo "  --help, -h            Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                                                    # Interactive mode"
        echo "  $0 --no-interactive                                   # Cron mode with default config"
        echo "  $0 --config /etc/vaultwarden/backup.conf --no-interactive  # Cron with custom config"
        echo ""
        echo "Behavior:"
        echo "  - If config exists: validates and runs backup"
        echo "  - If config not found: prompts for configuration and saves it"
        echo "  - With --no-interactive: only runs if valid config exists"
        exit 0
        ;;
esac

main