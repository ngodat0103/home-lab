#!/bin/bash
set -euo pipefail

LOG_LIB_URL="${LOG_LIB_URL:-https://raw.githubusercontent.com/ngodat0103/common-stuff/b54ce2aeff431309f89261039115165d8c368cc0/0-shell/7-log/log.sh}"

source <(curl -fsl ${LOG_LIB_URL}) || return

# Create a PVE user and an API token with full privileges (inherits the user's rights)
# Saves Terraform-friendly env vars to /root/<user>_api_token.env

require_root() {
  if [[ $(id -u) -ne 0 ]]; then
    print_error "This script must be run as root." >&2
    return
  fi
}

prompt_credentials() {
  read -rp "Enter username (default: akira): " USERNAME_INPUT || true
  if [[ -z "${USERNAME_INPUT:-}" ]]; then
    USERNAME_INPUT="akira"
  fi

  # If no realm is included, default to @pve
  if [[ "$USERNAME_INPUT" == *"@"* ]]; then
    USERID="$USERNAME_INPUT"
  else
    USERID="${USERNAME_INPUT}@pve"
  fi

  read -rp "Enter API token id (default: terraform): " TOKEN_ID || true
  TOKEN_ID="${TOKEN_ID:-terraform}"

  read -srp "Enter password for ${USERID}: " PW1; echo
  read -srp "Confirm password: " PW2; echo
  if [[ "$PW1" != "$PW2" ]]; then
    print_error "Passwords do not match. Aborting." >&2
    return
  fi
}

create_user() {
  if pveum user list | awk '{echo $1}' | grep -qx "$USERID"; then
    print_info "User $USERID already exists. Skipping creation."
  else
    print_info "Creating user $USERID ..."
    pveum user add "$USERID" --password "$PW1"
  fi

  print_info "Granting Administrator role to $USERID ..."
  pveum acl modify / --users "$USERID" --roles Administrator --propagate 1
}

create_token_full_priv() {
  print_info "Creating full-privilege API token ${USERID}!${TOKEN_ID} ..."
  TOKEN_JSON="$(pveum user token add "$USERID" "$TOKEN_ID" --privsep 0 --output-format json)"


  echo $TOKEN_JSON > /root/admin_token.json
  print_info "token saved at /root/admin_token.json"
}

create-admin-account() {
  require_root
  prompt_credentials
  create_user
  create_token_full_priv
  print_info "Done. User: $USERID with Administrator role. Token: ${USERID}!${TOKEN_ID}"
}