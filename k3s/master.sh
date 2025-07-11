apt install update
apt install -y nfs-common
curl https://baltocdn.com/helm/signing.asc | gpg --dearmor | sudo tee /usr/share/keyrings/helm.gpg > /dev/null
sudo apt-get install apt-transport-https --yes
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/helm.gpg] https://baltocdn.com/helm/stable/debian/ all main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list
sudo apt-get update
sudo apt-get install helm
curl -sfL https://get.k3s.io | K3S_TOKEN=supersecuretoken INSTALL_K3S_EXEC="server" sh -s - --flannel-iface=eth1
echo "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml" >> /root/.bashrc
helm repo add nfs-subdir-external-provisioner https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm upgrade --install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner --set nfs.server=192.168.57.13 --set nfs.path=/nfs/k3s/data --set storageClass.reclaimPolicy=Retain -n kube-system