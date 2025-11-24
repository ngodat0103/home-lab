#!/bin/bash

set -euo pipefail

SNAP_NAME="$1"
if [[ -z "$SNAP_NAME" ]]; then
  echo "Usage: $0 <snapshot-name>"
  exit 1
fi

get_vms_by_tag() {
  local tag="$1"
  pvesh get /cluster/resources --type vm --output-format json \
    | jq -r ".[] | select(.tags != null and (.tags | contains(\"$tag\"))) | .vmid"
}

# Get VM IDs for workers and masters
WORKERS=$(get_vms_by_tag "kubernetes-workers")
MASTERS=$(get_vms_by_tag "kubernetes-masters")

echo -e "📌 Workers:\n$WORKERS"
echo -e "📌 Masters:\n$MASTERS"

shutdown_vms() {
  local vms="$1"
  for vmid in $vms; do
    echo "🔻 Shutting down VM $vmid ..."
    qm shutdown "$vmid" --timeout 60 || true
  done
  # Wait until all are stopped
  for vmid in $vms; do
    echo "⏳ Waiting for VM $vmid to stop..."
    while qm status "$vmid" | grep -q "status: running"; do
      sleep 5
    done
    echo "✅ VM $vmid stopped."
  done
}
snapshot_vms() {
  local vms="$1"
  for vmid in $vms; do
    echo "📸 Taking snapshot $SNAP_NAME for VM $vmid ..."
    qm snapshot "$vmid" "$SNAP_NAME" --description "Automated snapshot: $SNAP_NAME"
  done
}
shutdown_vms "$WORKERS"
shutdown_vms "$MASTERS"

snapshot_vms "$WORKERS"
snapshot_vms "$MASTERS"

echo "🎉 All snapshots completed successfully!"

