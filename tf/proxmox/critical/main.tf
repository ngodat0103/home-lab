
locals {
  #Source: https://images.linuxcontainers.org/
  lxc_templates = {
    # alpine_3_22 = "https://images.linuxcontainers.org/images/alpine/3.22/amd64/tinycloud/20250818_13:00/rootfs.tar.xz"
    ubuntu_2204 = "https://images.linuxcontainers.org/images/ubuntu/noble/amd64/cloud/20250821_07%3A42/rootfs.tar.xz"
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
      node_name = local.node_name
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
      cores                    = 4
      memory                   = 8096
      node_name                = local.node_name
      mount_volume_size = 50 #GB
      vm_id                    = 100
      hostname                 = "postgresql-16.internal"
      tags = ["production","storage"]
    }
  }

  lan_gateway = "192.168.1.1"
}


module "network_default" {
  source         = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/network/private?ref=ef2db374546fe4bade20496d79bc50e6776db4cd"
  for_each       = local.network
  bridge_address = each.value.bridge_address
  node_name = local.node_name
  bridge_name    = each.key
  bridge_comment = each.value.bridge_comment
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
resource "proxmox_virtual_environment_download_file" "vm" {
  for_each     = local.vm_template
  file_name    = "${each.key}.qcow2"
  datastore_id = "local"
  content_type = "import"
  node_name    = local.node_name
  url          = each.value
}

module "lxc_production" {
  source                   = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/lxc?ref=ef2db374546fe4bade20496d79bc50e6776db4cd"
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
  tags = each.value.tags
  hostname                 = each.value.hostname
  mount_volume_size = each.value.mount_volume_size
  datastore_id = "local-lvm"
  mount_volume_name = "local-lvm"
}

module "ubuntu_server"{
  source = "git::https://github.com/ngodat0103/terraform-module.git//proxmox/vm?ref=ef2db374546fe4bade20496d79bc50e6776db4cd"
  template_image_id = resource.proxmox_virtual_environment_download_file.vm["ubuntu_2204"].id
  name = "UbuntuServer"
  tags = ["production","storage","main"]
  node_name = local.node_name
  ip_address = "192.168.1.121/24"
  hostname = "ubuntu-server.local"
  bridge_name = "vmbr0"
  memory = 8096
  gateway = local.lan_gateway
  protection = true
  vm_id = 101
  cpu_type = "host"
  boot_disk_size = 80
  cpu_cores = 4
  public_key = file("~/OneDrive/ssh/akira-ubuntu-server/root/id_rsa.pub")
  additional_disks = {
    sda2 ={
      path_in_datastore = "/dev/disk/by-id/ata-HGST_HTS721010A9E630_JR10006P1SSP5F"
      file_format = "raw"
      datastore_id = ""
      interface = "virtio1"
      size = 931
      backup = false
    }
  }
}
#Push metrics to influxdb hosted in Ubuntu vm
resource "proxmox_virtual_environment_metrics_server" "influxdb_server" {
  count =  var.influxdb_token == null ? 0 : 1
  name   = "influxdb-ubuntu-server"
  server = "192.168.1.121"
  port   = 8086
  type   = "influxdb"
  influx_organization = "proxmox"
  influx_bucket = "proxmox"
  influx_db_proto = "http"
  influx_token = var.influxdb_token
}