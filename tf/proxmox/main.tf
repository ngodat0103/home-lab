
locals {
  #Source: https://images.linuxcontainers.org/
  lxc_templates = {
    alpine_3_22 = "https://images.linuxcontainers.org/images/alpine/3.22/amd64/tinycloud/20250818_13:00/rootfs.tar.xz"
    ubuntu_2204 = "https://images.linuxcontainers.org/images/ubuntu/noble/amd64/cloud/20250818_07:42/rootfs.tar.xz"
  }
  vm_template = {
    #Reference: https://cloud-images.ubuntu.com/jammy/current/
    ubuntu_2204 = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  }
  network = {
    private = {
      bridge_address = "192.168.99.1/24"
      bridge_name    = "private"
      bridge_comment = "This network can't be reached from outside and is used for stateful applications."
    },
    lab = {
      bridge_name    = "lab"
      bridge_address = "192.168.40.1/24"
      bridge_comment = "Isolated network for my testing things"
    }
  }
  lxc = {
    postgresql_16 = {
      ip_address               = "192.168.99.2/24"
      gateway                  = "192.168.99.1"
      network_interface_name   = "fldskfjsd"
      network_interface_bridge = "private"
      template_file_id         = resource.proxmox_virtual_environment_download_file.lxc["ubuntu_2204"].id
      cores                    = 4
      memory                   = 4096
      node_name                = "pve"
      vm_id                    = 100
      hostname                 = "postgresql-16.internal"
    },
    nfs = {
      ip_address               = "192.168.99.3/24"
      gateway                  = "192.168.99.1"
      network_interface_name   = "nfs-default"
      template_file_id         = resource.proxmox_virtual_environment_download_file.lxc["ubuntu_2204"].id
      network_interface_bridge = "private"
      cores                    = 1
      memory                   = 1024
      vm_id                    = 101
      node_name                = "pve"
      hostname                 = "nfs.internal"
    },
    jellyfin = {
      ip_address               = "192.168.99.4/24"
      gateway                  = "192.168.99.1"
      network_interface_name   = "nfs-default"
      template_file_id         = resource.proxmox_virtual_environment_download_file.lxc["ubuntu_2204"].id
      network_interface_bridge = "private"
      cores                    = 4
      memory                   = 4096
      vm_id                    = 102
      node_name                = "pve"
      hostname                 = "jellyfin.internal"
    }
  }
}


module "network_default" {
  source         = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/network/private?ref=29d6a14d18ef468c41b80faec39ad0e70459bebe"
  for_each       = local.network
  bridge_address = each.value.bridge_address
  bridge_name    = each.key
  bridge_comment = each.value.bridge_comment
}
resource "proxmox_virtual_environment_download_file" "lxc" {
  for_each       = local.lxc_templates
  file_name      = "${each.key}.tar.xz"
  datastore_id   = "local"
  content_type   = "vztmpl"
  node_name      = "pve"
  url            = each.value
  upload_timeout = 10
}
resource "proxmox_virtual_environment_download_file" "vm" {
  for_each     = local.vm_template
  file_name    = "${each.key}.qcow2"
  datastore_id = "local"
  content_type = "import"
  node_name    = "pve"
  url          = each.value
}

module "lxc_production" {
  source                   = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/lxc?ref=29d6a14d18ef468c41b80faec39ad0e70459bebe"
  for_each                 = local.lxc
  ip_address               = each.value.ip_address
  gateway                  = each.value.gateway
  network_interface_name   = each.value.network_interface_name
  template_file_id         = each.value.template_file_id
  network_interface_bridge = each.value.network_interface_bridge
  cores                    = each.value.cores
  memory                   = each.value.memory
  vm_id                    = each.value.vm_id
  node_name                = each.value.node_name
  hostname                 = each.value.hostname
}

module "k8s_masters" {
  source            = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/vm?ref=29d6a14d18ef468c41b80faec39ad0e70459bebe"
  count             = 3
  template_image_id = resource.proxmox_virtual_environment_download_file.vm["ubuntu_2204"].id
  hostname          = "master-nodes-${count.index}.local"
  name              = "master-nodes-${count.index}"
  public_key        = file("/home/akira/.ssh/id_ed25519.pub")
  ip_address        = "192.168.1.10${count.index}/24"
  gateway           = "192.168.1.1"
  memory            = 2096
  cores             = 2
  node_name         = "pve"
  datastore_id      = "local-lvm"
  bridge_name       = "vmbr2"
  vm_id             = 300 + count.index
}
