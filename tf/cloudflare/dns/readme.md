# Cloudflare Configuration

This directory contains Terraform configurations for managing Cloudflare resources for the `datrollout.dev` domain.

## Features

- **Dynamic DNS**: Automatically updates DNS records with the current public IP address.
- **Firewall Rules**: Manages firewall rules to protect the services from unwanted traffic.
- **UptimeRobot Integration**: Allows health checks from UptimeRobot by automatically updating a list of their IP addresses.

## Usage

To use this configuration, run the following commands:

```bash
terraform init
terraform plan
terraform apply
```
