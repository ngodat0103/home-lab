# Ansible for Home Lab

This directory contains Ansible playbooks and configurations for automating the setup, provisioning, and management of my home lab environment.

## Overview

The primary goal of this Ansible setup is to codify the entire infrastructure, making it reproducible, version-controlled, and easy to manage. It covers everything from virtual machine provisioning on Proxmox to deploying applications and services in Docker containers and Kubernetes.

## Directory Structure

-   `docker/`: Contains playbooks for deploying and managing services running in Docker containers. The old settings from the bare metal server are planned to be migrated to vm/ubuntu-server.
-   `kubespray/`: Holds configurations and playbooks for deploying a Kubernetes cluster using Kubespray. (planned)
-   `proxmox/`: Includes playbooks for interacting with the Proxmox VE hypervisor
-   `service/`: Playbooks for managing specific services running on the servers, like PostgreSQL. The old settings from the bare metal server are planned to be migrated to vm/ubuntu-server.
-   `system-cron/`: Manages system-level cron jobs for tasks like backups. (The old settings from the bare metal server are planned to be migrated to vm/ubuntu-server.)
-   `vm/`: Contains playbooks for provisioning and configuring virtual machines, particularly Ubuntu Server.

## Getting Started

To run these playbooks, you will need Ansible installed. The main inventory is defined in `inventory.ini`.

## Playbook Details

Here is a breakdown of the individual playbook files and their purposes:

| File | Description |
| --- | --- |
| `docker/services/2-gitlab.yaml` | Deploys GitLab as a Docker service. |
| `docker/services/3-vaultwarden.yaml` | Deploys Vaultwarden (a Bitwarden server) as a Docker service. |
| `docker/services/4-traefik.yaml` | Deploys Traefik as a Docker service for reverse proxying. |
| `docker/services/5-postgres-exporter.yaml` | Deploys the PostgreSQL exporter as a Docker service. |
| `docker/services/files/prometheus.yaml` | Configuration file for Prometheus. |
| `docker/services/files/traefik.yaml` | Configuration file for Traefik. |
| `proxmox/grub.yaml` | Manages GRUB configuration on Proxmox nodes. |
| `proxmox/power.yaml` | Manages power states of Proxmox nodes or VMs. |
| `proxmox/storage.yaml` | Manages storage on Proxmox. |
| `service/postgresql-16/0-manage-postgresql.yaml` | Main playbook for managing PostgreSQL 16. |
| `service/postgresql-16/1-manage-hba.yaml` | Manages HBA (Host-Based Authentication) for PostgreSQL 16. |
| `service/postgresql-16/2-manage-interface.yaml` | Manages network interfaces for PostgreSQL 16. |
| `system-cron/backup.yaml` | Configures system-level cron jobs for backups. |
| `vm/ubuntu-server/apps/0-network.yaml` | Configures network settings for applications on Ubuntu servers. |
| `vm/ubuntu-server/apps/1-useless-app.yaml` | Deploys and configures a "useless-app" on Ubuntu servers. |
| `vm/ubuntu-server/apps/2-qbittorrent.yaml` | Deploys and configures qBittorrent on Ubuntu servers. |
| `vm/ubuntu-server/basic/apt.yaml` | Manages APT packages and repositories on Ubuntu servers. |
| `vm/ubuntu-server/basic/samba.yaml` | Configures Samba for file sharing on Ubuntu servers. |
| `vm/ubuntu-server/basic/storage.yaml` | Manages storage and filesystems on Ubuntu servers. |
| `vm/ubuntu-server/basic/user.yaml` | Manages users and groups on Ubuntu servers. |
| `vm/ubuntu-server/iptables.yaml` | Manages iptables rules for Ubuntu servers. |
| `vm/ubuntu-server/observation-and-monitoring/grafana/0-manage.yaml` | Manages the Grafana service on Ubuntu servers for monitoring. |
| `vm/ubuntu-server/observation-and-monitoring/grafana/files/alert.yaml` | Configures alerts in Grafana. |
| `vm/ubuntu-server/observation-and-monitoring/influxdb/0-manage.yaml` | Manages the InfluxDB service on Ubuntu servers for monitoring. |

