# Home Lab

Personal homelab for learning **production-grade Kubernetes deployment practices** before applying to family home server. Migrated from Ansible to **K3s + GitOps** for cloud-native infrastructure management.

## Objective

Learn and validate production best practices for:
- K3s cluster management and GitOps workflows
- High-availability application deployment
- Monitoring, alerting, and backup strategies
- Security and secret management
- Storage and networking solutions

**Goal**: Apply validated configurations to production home server.

## Tech Stack

**Infrastructure**: Vagrant, K3s, Flannel CNI, VirtualBox  
**GitOps**: ArgoCD, self-healing, automated sync  
**Storage**: Longhorn, NFS external provisioner  
**Networking**: Traefik ingress, SSL termination  
**Security**: Sealed Secrets, encrypted secret management  
**Monitoring**: Kube Prometheus Stack, Grafana, AlertManager  
**DNS**: Terraform + Cloudflare  
**Legacy**: Ansible (deprecated), Docker standalone (migrating)

## Structure

```
├── k3s/                # 🚀 Primary: K3s + GitOps applications
├── ansible/            # Legacy: Ansible playbooks (deprecated)
├── tf/                 # Terraform: Cloudflare DNS
└── common-stuff/       # Shared utilities and scripts
```

## Status

**✅ Lab Ready**: K3s cluster, ArgoCD GitOps, Traefik ingress, Longhorn storage, Sealed Secrets  
**🚧 Learning**: Monitoring stack, alerting rules, production patterns  
**🎯 Next**: Validate production-grade configurations for family server

## Applications

**✅ K3s Deployed**: Vaultwarden, qBittorrent, PostgreSQL, Traefik, ArgoCD  
**� Migrating**: GitLab, MinIO, Redis, Nextcloud

## Quick Start

**Requirements**: Vagrant, VirtualBox, kubectl, helm

```bash
cd k3s/
./start-cluster.sh     # Deploy 4-node K3s + ArgoCD
./shutdown-cluster.sh  # Graceful shutdown + volume detach
```

**Cluster**: 1 master + 2 workers + 1 NFS server (192.168.57.0/24)  
**Purpose**: Learning lab to validate patterns before production home server