# Home Lab

This repository contains the configuration for my personal home lab. It's a mono-repo for managing infrastructure, applications, and services using a variety of tools. This project is currently in the process of migrating services from Ansible to a Kubernetes-based setup using GitOps. It also serves as a safe and practical playground for me to learn and explore new concepts in the world of DevOps and infrastructure management.

## Overview

The goal of this project is to automate the setup and management of my home lab environment. This includes:
-   Provisioning virtual machines.
-   Configuring the operating system and services.
-   Deploying applications using containers and orchestration.
-   Managing DNS and network configurations.

## Technologies

This project uses the following technologies:

-   **Infrastructure as Code:**
    -   [Terraform](httpss://www.terraform.io/): For provisioning virtual machines on KVM (**Deprecated**) and managing Cloudflare DNS.
    -   [Vagrant](httpss://www.vagrantup.com/): For creating development environments.
-   **Configuration Management:**
    -   [Ansible](httpss://www.ansible.com/): For configuring the base system, installing software, and managing services.
-   **Containerization & Orchestration:**
    -   [Docker](httpss://www.docker.com/): For running containerized applications.
    -   [Kubernetes (K3s)](httpss://k3s.io/): For container orchestration.
    -   [ArgoCD](httpss://argo-cd.readthedocs.io/en/stable/): For GitOps and continuous deployment to Kubernetes.
-   **Monitoring & Observation:**
    -   [Prometheus](httpss://prometheus.io/): For metrics and alerting.
    -   [Grafana](httpss://grafana.com/): For visualization and dashboards.
    -   [Alloy](httpss://grafana.com/docs/alloy/latest/): For collecting telemetry data.

## Directory Structure

```
.
├── ansible/            # Ansible playbooks for configuration management
├── k3s/                # Kubernetes (K3s) cluster setup and ArgoCD applications
├── tf/                 # Terraform configurations for infrastructure provisioning
└── vagrant-template/   # Vagrant template for development environments
```

## Deployed Services

Here are some of the services running in the home lab:

-   **GitLab:** Self-hosted Git repository manager.
-   **Vaultwarden:** Self-hosted password manager (Bitwarden compatible).
-   **Traefik:** Reverse proxy and load balancer.
-   **qBittorrent:** BitTorrent client.
-   **MinIO:** S3 compatible object storage.
-   **PostgreSQL:** Relational database.
-   **Redis:** In-memory data store.
-   **Prometheus & Grafana:** Monitoring and observability stack.

## Getting Started

To get started with this project, you will need to have the following tools installed:
-   Terraform
-   Ansible
-   Vagrant
-   kubectl
-   helm

The setup is specific to my environment, but you can adapt it to your needs.

## License

This project is licensed under the MIT License.
