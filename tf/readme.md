# Terraform Infrastructure

This directory contains **modularized Terraform configurations** for managing cloud and on-premises infrastructure in the home lab. All modules are sourced from a central [GitHub Terraform module repository](https://github.com/ngodat0103/terraform-module), enabling code reuse and maintainability.

## Intention

The goal of this project is to manage the entire home lab infrastructure as code using Terraform. This includes cloud resources like DNS and firewall rules, as well as on-premises virtual machines and containers. By using Terraform, we can ensure that the infrastructure is reproducible, version-controlled, and easy to manage.

## Key Features

- **Modular Design**: All major resources (DNS, firewall, monitoring, VMs) are implemented as reusable modules from a dedicated GitHub repo.
- **Remote State Management**: Terraform state is securely stored in the cloud using HashiCorp Terraform Cloud (see `workspace.tf`).
- **Multi-Provider**: Integrates Cloudflare, KVM/libvirt, Proxmox, and UptimeRobot providers.
- **Automated DNS & Firewall**: Dynamic DNS and personal firewall rules managed via modules.
- **External Monitoring**: UptimeRobot monitors provisioned and managed as code.


## Structure

```
tf/
├── cloudflare/      # Cloudflare DNS, firewall, and related resources (modular)
├── kvm/             # KVM-based VM infrastructure (cloud-init, networking, modular) (deprecated in favor of Proxmox)
├── proxmox/         # Proxmox-based VM infrastructure (modular)
└── uptimerobot/     # UptimeRobot monitoring integration (modular)
```
- **cloudflare/**: Manages DNS records and firewall rules for the `datrollout.dev` domain. It uses a module to create DDNS records and another module for personal firewall rules. It also downloads a list of Uptime Robot IPs to allow health checks.
- **kvm/**: Provisions a KVM-based virtual machine using the `nv6/libvirt` provider. It creates a VM with a cloud-init configuration and a dedicated network. (deprecated in favor of Proxmox)
- **proxmox/**: Manages Proxmox-based virtual machines and networking. It uses modules to create a private network and an Ubuntu server VM. It also configures metrics to be pushed to an InfluxDB server.
- **uptimerobot/**: Manages UptimeRobot monitors for various services like GitLab, Vaultwarden, and Nextcloud.

## Usage

Each subdirectory is a standalone Terraform project. To use:

1. `cd` into the desired subdirectory (e.g., `cloudflare/`).
2. Initialize Terraform:
   ```bash
   terraform init
   ```
3. Review and apply changes:
   ```bash
   terraform plan
   terraform apply
   ```

## Prerequisites
- [Terraform](https://www.terraform.io/) >= 1.0
- API credentials for Cloudflare and UptimeRobot (see each subdirectory's `vars.tf` for details)
- Access to [ngodat0103/terraform-module](https://github.com/ngodat0103/terraform-module)

## State Management
Terraform state is stored remotely using [Terraform Cloud](https://app.terraform.io/)

---

_See the main project [README](../readme.md) for overall home lab context._