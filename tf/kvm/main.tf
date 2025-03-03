# Configure the Libvirt provider
terraform {
  required_providers {
    libvirt = {
      source = "nv6/libvirt"
      version = "0.7.1"
    }
  }
}

provider "libvirt" {
  uri = "qemu:///system"
}

resource "libvirt_volume" "ubuntu_2204_disk" {
  name   = "duc-ubuntu2204-vm.qcow2"
  pool   = "default"
  source = "https://cloud-images.ubuntu.com/releases/22.04/release-20250228/ubuntu-22.04-server-cloudimg-amd64-disk-kvm.img"
}
resource "libvirt_volume" "duc_vm_disk" {
  name   = "duc-vm-disk.qcow2"
  pool   = "default"
  base_volume_id = libvirt_volume.ubuntu_2204_disk.id
  size  = 21474836480
}

data "template_file" "user_data" {
  template = file("${path.module}/cloud_init.cfg")
}
data "template_file" "network_config" {
  template = file("${path.module}/network_config.cfg")
}
resource "libvirt_cloudinit_disk" "commoninit" {
  name           = "commoninit.iso"
  user_data      = data.template_file.user_data.rendered
  network_config = data.template_file.network_config.rendered
  pool           = "default"
}

# Define a new virtual network
resource "libvirt_network" "duc-network" {
  name      = "duc-network"
  mode      = "route"
  domain    = "my-network.local"
  addresses = ["192.168.100.0/24"]
  autostart = true

  dhcp {
    enabled = true
  }

  dns {
    enabled = true
  }
}

resource "libvirt_domain" "duc_vm" {
  name   = "duc-ubuntu-vm"
  memory = 2048
  vcpu   = 1
   cpu {
    mode = "host-passthrough"
  }
  cloudinit = libvirt_cloudinit_disk.commoninit.id
  disk {
    volume_id = libvirt_volume.duc_vm_disk.id
  }

  network_interface {
    network_name = libvirt_network.duc-network.name
  }
   console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }
}