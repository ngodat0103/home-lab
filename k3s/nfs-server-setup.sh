apt update
apt install nfs-kernel-server
mkdir -p /nfs/k3s/data/retain
mkdir -p /nfs/k3s/data/delete
chown nobody:nogroup /nfs/k3s/data
chmod 777 -R /nfs/k3s/data
echo "/nfs/k3s/data 192.168.57.0/24(rw,sync,no_subtree_check,no_root_squash)" >> /etc/exports
systemctl restart nfs-kernel-server