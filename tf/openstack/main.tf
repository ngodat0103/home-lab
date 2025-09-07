resource "openstack_networking_network_v2" "karina" {
  name           = "karina"
  admin_state_up = "true"
}

resource "openstack_networking_subnet_v2" "karina" {
  name       = "karina"
  network_id = openstack_networking_network_v2.karina.id
  cidr       = "192.168.199.0/24"
  ip_version = 4
}

resource "openstack_networking_secgroup_v2" "secgroup_1" {
  name        = "secgroup_1"
  description = "a security group"
}

resource "openstack_networking_secgroup_rule_v2" "secgroup_rule_1" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.secgroup_1.id
}
resource "openstack_compute_keypair_v2" "karina" {
  name       = "karina"
  public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQD1mqJ9VFW25ZILkw2pDbnFaa59O0pBIEDbT/V9R/HZT53Jgq+MNnS1pUAyIXEpu6Rf+HqiqhXtnwlnw2dLhL3VYiGFNA/ZxK7Jgemr1uQqgYNqtNQbFz4LBsN3/oR2gW4wFCUqS0CqA25xV30RhO0VRZEf1Ks+unCwbY8xQUsjTPYC5ief7OmGmP/fouTn84M04njptzRHfeJ1YAmm5PX1hewyaZN3zhW8R/6kHvqLg492/ywJ3Fh3qZk8Qu2STzPwfDRRzwuGkKEuO6itl9awe6uWE8gFGZoUsIQt3hjU2GCmLCvj2My+HCUBH1yz/aUo5iQuTbQFdDlwOIRppa+4ZsawHUSZnBrgzXjn3HGYb6XGNuWBzjXm2+XHlomex/5I3/sxCjVoME/IYgZxoGVPeJZSQ6cOYjU6PYK3+ygkbgWqVYrkBC0BJGruoAsDo5SUv27ShxIs7vZple+U3AhthGiCbjvSIv5GwpJwnYcHDcH46N35mTJNkweQzEHrqQ8= ngovu@LAPTOP-9NBAONU6"
}


resource "openstack_networking_router_v2" "karina" {
  name                = "karina"
  admin_state_up      = true
  external_network_id = "c3455e8f-ea16-4f5d-ad5e-5c4292015a0d"
}

resource "openstack_networking_router_interface_v2" "router_interface_1" {
  router_id = openstack_networking_router_v2.karina.id
  subnet_id = openstack_networking_subnet_v2.karina.id
}


resource "openstack_compute_instance_v2" "karina" {
  name            = "karina"
  image_name      = "Ubuntu 22.04"
  flavor_name     = "d30.l4"
  key_pair        = openstack_compute_keypair_v2.karina.name
  security_groups = [openstack_networking_secgroup_v2.secgroup_1.name]
  network {
    name = openstack_networking_subnet_v2.karina.name
  }
}
data "openstack_networking_port_v2" "karina" {
  device_id = openstack_compute_instance_v2.karina.id
}
resource "openstack_networking_floatingip_v2" "karina" {
  pool = "Public_Net"
}
resource "openstack_networking_floatingip_associate_v2" "karina" {
  floating_ip = openstack_networking_floatingip_v2.karina.address
  port_id     = data.openstack_networking_port_v2.karina.id
}