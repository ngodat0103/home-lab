#!/bin/bash
set -e
source <(curl -fsSL https://raw.githubusercontent.com/ngodat0103/common-stuff/refs/heads/main/scripts/argocd/enable-self-heal.sh)
START_VM_SCRIPT=$(cat <<'EOF'
#!/bin/bash
set -e
get_vms_by_tags() {
  local tag1="$1"
  local tag2="$2"
  pvesh get /cluster/resources --type vm --output-format json \
    | jq -r --arg t1 "$tag1" --arg t2 "$tag2" '
      .[]
      | select(.tags? != null)
      | select((.tags | split(";") | index($t1)) and (.tags | split(";") | index($t2)))
      | .vmid
    '
}
start_vms() {
  local vms="$1"
  for vmid in $vms; do
    echo "🚀 Starting VM $vmid ..."
    qm start "$vmid" || true
  done
  # Wait until all are running
  for vmid in $vms; do
    echo "⏳ Waiting for VM $vmid to be running..."
    while ! qm status "$vmid" | grep -q "status: running"; do
      sleep 5
    done
    echo "✅ VM $vmid is running."
  done
}

# --- Collect VM IDs ---
WORKERS=$(get_vms_by_tags "Development" "Kubernetes-workers")
MASTERS=$(get_vms_by_tags "Development" "Kubernetes-masters")

echo -e "📌 Workers:\n$WORKERS"
echo -e "📌 Masters:\n$MASTERS"

# --- Start sequence ---
start_vms "$MASTERS"
start_vms "$WORKERS"
EOF
)

# 🚀 Execute remotely on Proxmox
ssh proxmox "bash -s" <<< "$START_VM_SCRIPT"
echo "⏳ Waiting for Kubernetes API to be ready..."
until kubectl version >/dev/null 2>&1; do
  sleep 5
done
echo "✅ Kubernetes cluster is available."

echo "⏳ Waiting for all nodes to be Ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=300s
echo "✅ All nodes are Ready."

# Post start
enable_argocd_self_heal