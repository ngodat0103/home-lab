terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
  }
}
locals {
        storageName = "backup-storage-prod"
}
resource "cloudflare_r2_bucket" "backupStorage" {
  account_id    = "4c8ad4e9fa8213af3fd284bb97b68b5e"
  name          = local.storageName
  location      = "apac"
  storage_class = "Standard"
}