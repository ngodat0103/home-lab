terraform {
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "3.3.2"
    }
  }
}

provider "openstack" {
  cloud = "openstack"
}

