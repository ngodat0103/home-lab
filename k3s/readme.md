# K3s Homelab Migration

This repository contains a personal lab environment to **practice, test, and validate the migration process** from standalone Docker deployments to a lightweight Kubernetes cluster using [K3s](https://k3s.io/).

> ⚠️ **Note**: This is a test environment used to evaluate concepts, configurations, and stability **before applying them to my real physical server**.

---

## Key Features

- **Lightweight Kubernetes**: Utilizes [K3s](https://k3s.io/) for a minimal, easy-to-manage Kubernetes distribution.
- **Infrastructure as Code**: Uses [Vagrant](https://www.vagrantup.com/) to define and provision the virtualized lab environment.
- **GitOps**: Employs [ArgoCD](https://argo-cd.readthedocs.io/en/stable/) for declarative, Git-based management of applications and configurations.
- **Ingress Controller**: Configured [Traefik](https://traefik.io/traefik/) for ingress and network management.
- **Monitoring**: Integrates the [Kube Prometheus Stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack) for a comprehensive monitoring solution.

---

## Current Migration Plan

### 1. PostgreSQL Database
- [X] Configure instance
- [X] Set up database schemas
- [X] Migrate data
- [ ] Implement backup and restore procedures

### 2. Vaultwarden
- [X] Deploy application
- [X] Migrate existing data
- [X] Set up automated backups using Kubernetes cronjob

### 3. GitLab
- [ ] Configure GitLab instance
- [ ] Migrate repositories and data
- [ ] Implement backup and restore strategy

### 4. Monitoring
- [X] Deploy Kube Prometheus Stack
- [ ] Configure dashboards and alerts
- [ ] Set up persistent storage for metrics

---

## Directory Structure

```
.
├── argocd-app/       # ArgoCD application definitions
├── argocd-crd/         # ArgoCD Helm chart and CRDs
├── postgresql/       # PostgreSQL instance and database configurations
├── traefik/          # Traefik ingress configuration
├── master.sh         # Script to provision the master node
├── worker.sh         # Script to provision worker nodes
├── Vagrantfile       # Vagrant configuration for the lab environment
└── readme.md         # This file
```

---

## How It Works

This project uses Vagrant to create a local K3s cluster and ArgoCD to manage the applications in a GitOps fashion.

1.  **Infrastructure Provisioning**: The `Vagrantfile` defines a multi-machine setup with a K3s master and several worker nodes. Running `vagrant up` will create these virtual machines, install K3s, and set up the basic cluster infrastructure.

2.  **GitOps with ArgoCD**: ArgoCD is installed on the cluster and configured to monitor this Git repository. Any changes pushed to the `main` branch that affect the Kubernetes manifests in the `argocd-app/` directory will be automatically detected by ArgoCD.

3.  **Application Deployment**: ArgoCD synchronizes the state of the applications defined in the repository with the state of the cluster. This means it will automatically deploy or update applications like Vaultwarden, PostgreSQL, and others whenever the corresponding manifests are updated in Git.