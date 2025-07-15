set -euo pipefail

echo "Disabling swap..."

# 1. Turn off all active swap
sudo swapoff -a

# 2. Comment out any swap entries in /etc/fstab to prevent swap re-enabling on reboot
sudo sed -i.bak '/\sswap\s/s/^/#/' /etc/fstab

# 3. (Optional) Remove the default swapfile if it exists
if [ -f /swapfile ]; then
    sudo rm -f /swapfile
    echo "/swapfile removed."
fi

# 4. Confirm swap is disabled
if swapon --summary | grep -q '^'; then
    echo "Warning: Swap still active!"
else
    echo "Swap successfully disabled."
fi
apt update
apt install -y nfs-common
curl -sfL https://get.k3s.io | K3S_URL="https://192.168.57.10:6443" K3S_TOKEN=supersecuretoken INSTALL_K3S_EXEC="agent" sh -s - --flannel-iface=eth1