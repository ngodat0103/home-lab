
locals {
  #Source: https://images.linuxcontainers.org/
  lxc_templates = {
    ubuntu_2204 = "https://images.linuxcontainers.org/images/ubuntu/jammy/amd64/cloud/20250826_07:42/rootfs.tar.xz"
  }

  vm_template = {
    #Reference: https://cloud-images.ubuntu.com/jammy/current/
    ubuntu_2204 = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  }
  node_name = "pve-master"
  network = {
    private = {
      bridge_address = "192.168.99.1/24"
      bridge_name    = "private"
      node_name      = local.node_name
      bridge_comment = "This network can't be reached from outside and is used for stateful applications."
    },
  }
  lxc = {
    postgresql_16 = {
      ip_address               = "192.168.99.2/24"
      gateway                  = "192.168.99.1"
      network_interface_name   = "eth0"
      network_interface_bridge = "private"
      template_file_id         = resource.proxmox_virtual_environment_download_file.lxc["ubuntu_2204"].id
      cores                    = 1
      memory                   = 1024*4
      node_name                = local.node_name
      mount_volume_size        = 50 #GB
      vm_id                    = 100
      hostname                 = "postgresql-16.internal"
      tags                     = ["production", "database"]
      protection               = true
      startup_config = {
        order      = 1
        up_delay   = 10
        down_delay = 10
      }
    }
  }
  lan_gateway = "192.168.1.1"
  k8s_public_key = file("~/OneDrive/ssh/k8s/id_rsa.pub")
}
module "network_default" {
  source         = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/network/private?ref=ef2db374546fe4bade20496d79bc50e6776db4cd"
  for_each       = local.network
  bridge_address = each.value.bridge_address
  node_name      = local.node_name
  bridge_name    = each.key
  bridge_comment = each.value.bridge_comment
}
resource "proxmox_virtual_environment_download_file" "vm" {
  for_each     = local.vm_template
  file_name    = "${each.key}.qcow2"
  datastore_id = "local"
  content_type = "import"
  node_name    = local.node_name
  url          = each.value
}
module "ubuntu_server" {
  source            = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/vm?ref=0b07dc767d9b6a5a75613dcf333ea79a9066ad8d"
  template_image_id = resource.proxmox_virtual_environment_download_file.vm["ubuntu_2204"].id
  name              = "UbuntuServer"
  tags              = ["production", "file-storage","public-facing","reverse-proxy"]
  node_name         = local.node_name
  ip_address        = "192.168.1.121/24"
  hostname          = "ubuntu-server.local"
  bridge_name       = "vmbr0"
  memory            = 1024*12
  gateway           = local.lan_gateway
  protection        = true
  vm_id             = 101
  cpu_type          = "host"
  boot_disk_size    = 256
  cpu_cores         = 4
  public_key        = file("~/OneDrive/ssh/akira-ubuntu-server/root/id_rsa.pub")
  network_model     = "e1000e"
  startup_config = {
    order      = 2
    up_delay   = 10
    down_delay = 10
  }
  additional_disks = {
    data1 = {
      path_in_datastore = "/dev/disk/by-id/ata-ST500DM002-1BD142_Z3TX81A7"
      file_format       = "raw"
      datastore_id      = ""
      interface         = "virtio1"
      size              = 465
      backup            = false
    },
    data2 = {
      path_in_datastore = "/dev/disk/by-id/ata-HGST_HTS721010A9E630_JR10006P1SSP5F"
      file_format       = "raw"
      datastore_id      = ""
      interface         = "virtio2"
      size              = 931
      backup            = false
    }
  }
}

module "teleport" {
  source            = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/vm?ref=53360d70fe4b7e165a0df761867d4965e3585de9"
  template_image_id = resource.proxmox_virtual_environment_download_file.vm["ubuntu_2204"].id
  name              = "Teleport"
  tags              = ["infra-access","public-facing"]
  node_name         = local.node_name
  ip_address        = "192.168.1.122/24"
  hostname          = "teleport.local"
  bridge_name       = "vmbr0"
  memory            = 1024*2
  gateway           = local.lan_gateway
  protection        = false
  boot_disk_size    = 30
  cpu_cores         = 1
  public_key        = file("~/OneDrive/ssh/teleport/id_rsa.pub")
  network_model     = "e1000e"
  startup_config = {
    order      = 3
    up_delay   = 60
    down_delay = 60
  }
}
#Push metrics to influxdb hosted in Ubuntu vm
resource "proxmox_virtual_environment_metrics_server" "influxdb_server" {
  count               = var.influxdb_token == null ? 0 : 1
  name                = "influxdb-ubuntu-server"
  server              = "192.168.1.121"
  port                = 8086
  type                = "influxdb"
  influx_organization = "proxmox"
  influx_bucket       = "proxmox"
  influx_db_proto     = "http"
  influx_token        = var.influxdb_token
}
resource "proxmox_virtual_environment_download_file" "lxc" {
  for_each       = local.lxc_templates
  file_name      = "${each.key}.tar.xz"
  datastore_id   = "local"
  content_type   = "vztmpl"
  node_name      = local.node_name
  url            = each.value
  upload_timeout = 10
}
module "lxc_production" {
  source                   = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/lxc?ref=1a2c9b342cdee0fc3e257daf09d750d88c0e83c8"
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
  tags                     = each.value.tags
  hostname                 = each.value.hostname
  mount_volume_size        = each.value.mount_volume_size
  protection               = each.value.protection
  startup_config           = each.value.startup_config
  datastore_id             = "local-lvm"
  mount_volume_name        = "local-lvm"
}

module "k8s_masters" {
  source            = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/vm?ref=0b07dc767d9b6a5a75613dcf333ea79a9066ad8d"
  count             = 3
  template_image_id = resource.proxmox_virtual_environment_download_file.vm["ubuntu_2204"].id
  hostname          = "master-nodes-${count.index}.local"
  name              = "master-nodes-${count.index}"
  public_key        = local.k8s_public_key
  ip_address        = "192.168.1.13${count.index}/24"
  tags              = ["Development", "Kubernetes-masters"]
  gateway           = "192.168.1.1"
  memory            = 4096
  cpu_cores         = 2
  node_name         = local.node_name
  boot_disk_size    = 50
  datastore_id      = "local-lvm"
  bridge_name       = "vmbr0"
  vm_id             = 300 + count.index
  startup_config = {
    order      = 3
    up_delay   = 10
    down_delay = 10
  }
}
module "k8s_workers" {
  source            = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/vm?ref=0b07dc767d9b6a5a75613dcf333ea79a9066ad8d"
  count             = 4
  template_image_id = resource.proxmox_virtual_environment_download_file.vm["ubuntu_2204"].id
  hostname          = "worker-nodes-${count.index}.local"
  name              = "worker-nodes-${count.index}"
  public_key        = local.k8s_public_key
  ip_address        = "192.168.1.14${count.index}/24"
  tags              = ["Development", "Kubernetes-workers"]
  boot_disk_size    = 100
  gateway           = "192.168.1.1"
  memory            = 1024*8
  cpu_cores         = 4
  node_name         = local.node_name
  datastore_id      = "local-lvm"
  bridge_name       = "vmbr0"
  vm_id             = 310 + count.index
  startup_config = {
    order      = 4
    up_delay   = 30
    down_delay = 30
  }
}

