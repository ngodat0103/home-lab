terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "0.82.0"
    }
  }
}
provider "proxmox" {
  endpoint = var.proxmox_endpoint

  username = var.proxmox_username
  password = var.proxmox_password

  # because self-signed TLS certificate is in use
  insecure = true
  ssh {
    username = "vagrant"
    # Lab only 
    private_key = file("./.vagrant/machines/default/virtualbox/private_key")


    #Real
    #private_key = file("~/.ssh/private_key")

    node {
      name    = "pve"
      address = "192.168.1.65"
    }
  }
}