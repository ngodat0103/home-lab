# K3s Homelab Migration

This repository contains a personal lab environment to **practice, test, and validate the migration process** from standalone Docker deployments to a lightweight Kubernetes cluster using [K3s](https://k3s.io/).

> ⚠️ **Note**: This is a test environment used to evaluate concepts, configurations, and stability **before applying them to my real physical server**.

---

## Key Features

- **Lightweight Kubernetes**: K3s cluster with Flannel CNI, NFS storage provisioner
- **Infrastructure as Code**: Vagrant + VirtualBox (4-node cluster: 1 master, 2 workers, 1 NFS server)
- **GitOps**: ArgoCD with self-healing, automated sync from Git repository
- **Storage**: Longhorn distributed storage + NFS external provisioner
- **Ingress**: Traefik with SSL termination and middleware
- **Security**: Sealed Secrets for secret management
- **Monitoring**: Kube Prometheus Stack (Prometheus, Grafana, AlertManager)
- **Applications**: PostgreSQL, Redis, MinIO, Nextcloud, qBittorrent, Vaultwarden

---

## Current Migration Status

### Infrastructure ✅
- [X] 4-node Vagrant cluster (1 master + 2 workers + NFS server)
- [X] K3s with Flannel CNI and Helm integration
- [X] NFS external provisioner for persistent storage
- [X] Longhorn distributed storage system

### Core Services ✅
- [X] ArgoCD GitOps with self-healing enabled
- [X] Traefik ingress controller with SSL
- [X] Sealed Secrets for secret management
- [ ] Kube Prometheus Stack monitoring
- [ ] ArgoCD notification system (Slack/Discord/email integration)
- [ ] Grafana alerting rules for critical issues

### Applications
- [X] PostgreSQL database
- [X] Vaultwarden password manager with automated backups
- [X] qBittorrent torrent client
- [ ] Redis cache server
- [ ] MinIO object storage
- [ ] Nextcloud file sharing platform

### Monitoring & Observability ✅
- [ ] Prometheus metrics collection
- [ ] Grafana dashboards
- [ ] AlertManager notifications
- [ ] Persistent storage for metrics
- [ ] Critical alert rules (pod failures, resource exhaustion, service downtime)
- [ ] ArgoCD sync failure notifications
- [ ] Multi-channel alerting (Discord, email)

---

## Planned Features

### Notification & Alerting System
- **ArgoCD Notifications**: Configure webhook/email notifications for deployment failures, sync errors, and health status changes
- **Grafana Alert Rules**: Critical monitoring for:
  - Pod crash loops and restart counts
  - Node resource exhaustion (CPU, memory, disk)
  - Service endpoint failures
  - Persistent volume issues
  - ArgoCD application out-of-sync alerts
- **Multi-Channel Delivery**: Slack, Discord, email integration for different severity levels
- **Alert Routing**: Critical alerts to immediate channels, warnings to daily digest

---

## Directory Structure

```
.
├── argocd/                    # ArgoCD configurations
│   ├── argocd-app/           # Application definitions
│   │   ├── daemon/           # DaemonSet apps (kube-prometheus-stack)
│   │   ├── stateful/         # Stateful apps (PostgreSQL, Redis, MinIO, etc.)
│   │   └── stateless/        # Stateless apps (Traefik, Vaultwarden, Sealed Secrets)
│   ├── argocd-crd/          # ArgoCD CRDs and Helm charts
│   └── projects/            # ArgoCD project definitions
├── postgresql/              # PostgreSQL configurations
├── qbittorrent/            # qBittorrent torrent client
├── traefik/                # Traefik ingress controller
├── vaultwarden/            # Vaultwarden password manager
├── master.sh               # K3s master node setup (swap disable, NFS, Helm, k3s server)
├── worker.sh               # K3s worker node setup (swap disable, NFS, k3s agent)
├── nfs-server-setup.sh     # NFS server configuration
├── start-cluster.sh        # Cluster startup + ArgoCD self-healing
├── shutdown-cluster.sh     # Graceful shutdown with Longhorn volume detach
├── Vagrantfile            # 4-node cluster definition
└── k3s.yaml               # Kubeconfig file
```

## Scripts & Automation

### Cluster Management
- `start-cluster.sh`: Vagrant up + ArgoCD self-healing activation
- `shutdown-cluster.sh`: Graceful shutdown with Longhorn volume detachment
- `master.sh`: Swap disable, NFS client, Helm install, K3s server, NFS provisioner setup
- `worker.sh`: Swap disable, NFS client, K3s agent join
- `nfs-server-setup.sh`: NFS kernel server setup with shared volumes

### Key Technologies
- **Vagrant**: Multi-machine virtualization (Ubuntu 22.04 LTS)
- **K3s**: Lightweight Kubernetes with Flannel CNI
- **Storage**: Longhorn + NFS external provisioner (retain/delete policies)
- **GitOps**: ArgoCD auto-sync with self-healing from external script
- **Networking**: Private network (192.168.57.0/24), Traefik ingress
- **Secrets**: Sealed Secrets controller for encrypted secret management
- **Alerting**: Prometheus AlertManager + Grafana rules (planned)
- **Notifications**: ArgoCD webhooks + multi-channel delivery (planned)

---

## How It Works

This project uses Vagrant to create a local K3s cluster and ArgoCD to manage the applications in a GitOps fashion.

1.  **Infrastructure Provisioning**: The `Vagrantfile` defines a 4-machine setup (1 master, 2 workers, 1 NFS server). The `start-cluster.sh` script runs `vagrant up` and enables ArgoCD self-healing.

2.  **GitOps with ArgoCD**: ArgoCD monitors this Git repository with automatic sync. Applications are organized by type (daemon/stateful/stateless) and deployed based on manifest changes.

3.  **Storage Strategy**: Combines Longhorn distributed storage with NFS external provisioner. Longhorn handles block storage while NFS provides shared filesystem access.

4.  **Application Deployment**: ArgoCD synchronizes applications from the `argocd-app/` directory structure, automatically deploying PostgreSQL, Vaultwarden, qBittorrent, monitoring stack, and other services.