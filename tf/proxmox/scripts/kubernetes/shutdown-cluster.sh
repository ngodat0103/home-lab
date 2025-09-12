#!/bin/bash
source <(curl -fsSL https://raw.githubusercontent.com/ngodat0103/common-stuff/refs/heads/main/scripts/log/log.sh)

SHUTDOWN_K8S_CLUSTER_SCRIPT=$(cat <<'EOF'
get_vms_by_tag() {
  local tag="$1"
  pvesh get /cluster/resources --type vm --output-format json \
    | jq -r ".[] | select(.tags != null and (.tags | contains(\"$tag\"))) | .vmid"
}

# Get VM IDs for workers and masters
WORKERS=$(get_vms_by_tag "Kubernetes-workers")
MASTERS=$(get_vms_by_tag "Kubernetes-masters")

echo -e "📌 Workers:\n$WORKERS"
echo -e "📌 Masters:\n$MASTERS"

shutdown_vms() {
  local vms="$1"
  for vmid in $vms; do
    echo "🔻 Shutting down VM $vmid ..."
    qm shutdown "$vmid" --timeout 300 &
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
shutdown_vms "$WORKERS"
shutdown_vms "$MASTERS"
EOF
)
ssh proxmox 'bash -s' <<< $SHUTDOWN_K8S_CLUSTER_SCRIPT
