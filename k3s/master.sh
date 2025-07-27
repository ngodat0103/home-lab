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
curl https://baltocdn.com/helm/signing.asc | gpg --dearmor | sudo tee /usr/share/keyrings/helm.gpg > /dev/null
sudo apt-get install apt-transport-https --yes
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/helm.gpg] https://baltocdn.com/helm/stable/debian/ all main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list
sudo apt-get update
sudo apt-get install helm
curl -sfL https://get.k3s.io | K3S_TOKEN=supersecuretoken INSTALL_K3S_EXEC="server" sh -s - --flannel-iface=eth1
echo "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml" >> /root/.bashrc
echo "alias kns=\"kubectl config set-context --current --namespace \"" >> /root/.bashrc
echo "alias kgp=\"kubectl get pod\"" >>/root/.bashrc
echo "alias kl=\"kubectl logs -f \"" >> /root/.bashrc
helm repo add nfs-subdir-external-provisioner https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm upgrade --install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner --set nfs.server=192.168.57.13 --set nfs.path=/nfs/k3s/data/retain --set storageClass.reclaimPolicy=Retain -n kube-system
cp /etc/rancher/k3s/k3s.yaml /vagrant/k3s.yaml
cd /vagrant
sed -i 's|server: https://127.0.0.1:6443|server: https://192.168.57.10:6443|' k3s.yaml
