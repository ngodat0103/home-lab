apt install update
apt install -y nfs-common
curl -sfL https://get.k3s.io | K3S_URL="https://192.168.57.10:6443" K3S_TOKEN=supersecuretoken INSTALL_K3S_EXEC="agent" sh -s - --flannel-iface=eth1