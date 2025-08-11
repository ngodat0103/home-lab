# Terraform Infrastructure

This directory contains **modularized Terraform configurations** for managing cloud and on-premises infrastructure in the home lab. All modules are sourced from a central [GitHub Terraform module repository](https://github.com/ngodat0103/terraform-module), enabling code reuse and maintainability.

## Key Features

- **Modular Design**: All major resources (DNS, firewall, monitoring, VMs) are implemented as reusable modules from a dedicated GitHub repo.
- **Remote State Management**: Terraform state is securely stored in the cloud using HashiCorp Terraform Cloud (see `workspace.tf`).
- **Multi-Provider**: Integrates Cloudflare, KVM/libvirt, and UptimeRobot providers.
- **Automated DNS & Firewall**: Dynamic DNS and personal firewall rules managed via modules.
- **External Monitoring**: UptimeRobot monitors provisioned and managed as code.


## Structure

```
tf/
├── cloudflare/      # Cloudflare DNS, firewall, and related resources (modular)
├── kvm/             # KVM-based VM infrastructure (cloud-init, networking, modular)
└── uptimerobot/     # UptimeRobot monitoring integration (modular)
```
- **cloudflare/**: Uses modules for DNS records and personal firewall, all sourced from the GitHub module repo.
- **kvm/**: Provisions VMs and networking using the `nv6/libvirt` provider and custom modules.
- **uptimerobot/**: Manages monitors using a dedicated module from the GitHub repo.

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
