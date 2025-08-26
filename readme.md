# Overview
Welcome to my homelab, this is where I apply best practice to manage my own server and virtualization for lab. 

# Status
I currently migrate from Ubuntu bare metal (death machine) to VM Ubuntu created by Proxmox

## Structure

The repository is organized into the following directories:

-   `k3s/`: Contains all the resources for the K3s cluster. # Inten to lab, not critical
    -   `argocd/`: Holds the ArgoCD applications for GitOps.
    -   `traefik/`: Contains Traefik configurations.
    -   `Vagrantfile`: Defines the Vagrant setup for the cluster nodes.
    -   `*.sh`: Scripts to manage the lifecycle of the cluster (startup, shutdown, node setup).

-   `ansible/`: Ansible playbooks used for the initial setup.
    -   `docker/`: Playbooks to deploy Docker services (migrating to `vm/ubuntu-server` from bare metal).
    -   `service/`: Playbooks for various services. (migrating to `vm/ubuntu-server` from bare metal).
    -   `vm/`: Playbooks to set up virtual machines.
    -   `proxmox/`: Playbooks to manage Proxmox 

-   `tf/`: Contains Terraform configurations for managing cloud resources.
    -   `cloudflare/`: Manages DNS records on Cloudflare.
    -   `kvm/`: Manages KVM virtual machines.
    -   `proxmox/`: Manages Proxmox resources.
    -   `uptimerobot/`: Manages monitoring with Uptime Robot.

-   `common-stuff/`: Shared utilities and scripts

## Specifications

-   **CPU**: 56 x Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz (2 Sockets)
-   **Kernel Version**: Linux 6.14.8-2-pve (2025-07-22T10:04Z)
-   **Boot Mode**: Legacy BIOS
-   **Proxmox VE Manager Version**: pve-manager/9.0.3/025864202ebb6109
-   **Memory**: 62GB
-   **Disk**:
    -   `sda`: 465.8G ST500DM002-1BD142    Z3TX81A7
        -   `sda1`: 465.8G
    -   `sdb`: 931.5G HGST HTS721010A9E630 JR10006P1SSP5F
        -   `sdb1`: 791.6G
        -   `sdb2`: 139.9G
    -   `nvme0n1`: 1.8T WDS200T3X0C-00SJG0   203990800463

