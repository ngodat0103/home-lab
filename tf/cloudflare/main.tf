terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
  }
}
provider "cloudflare" {
  api_token = local.cloudflare_api_token
}
locals {
  cloudflare_api_token = var.cloudflare_api_token
  zone_id              = "ab6606e8b3aad0b66008eb26f2dd3660"
  share_comment        = "Managed by Terraform"
  account_id           = "4c8ad4e9fa8213af3fd284bb97b68b5e"
}
module "ddns_records" {
  source               = "git::https://github.com/ngodat0103/terraform-module.git//cloudflare/dns-records?ref=9efc538229c94814818587dccad17a7ccf878310"
  cloudflare_api_token = local.cloudflare_api_token
  zone_id              = local.zone_id
  share_comment        = local.share_comment
  ddns_content         = var.ddns_content
  dns_records = {
    nextcloud = {
      type = "CNAME"
      proxied = true
      ttl = 360
    }
    jellyfin = {
      type = "CNAME"
      proxied = false
    }
    gitlab = {
      type = "CNAME"
      proxied = true
    }
    bitwarden = {
      type = "CNAME"
      proxied = true
    }
  }
}

## Firewall
resource "null_resource" "download_uptimerobot_ips" {
  provisioner "local-exec" {
    command = "curl -o ${path.root}/uptimerobot-ips.txt https://uptimerobot.com/inc/files/ips/IPv4.txt"
  }
  triggers = {
    always_run = "${timestamp()}"
  }
}


import {
  to = module.personal_firewall.cloudflare_ruleset.default
  id = "zones/${local.zone_id}/1036fedd818d45d78dbad2f5dcf4cb17"
}

module "personal_firewall" {
  source               = "git::https://github.com/ngodat0103/terraform-module.git//cloudflare/personal-firewall?ref=0.0.1"
  cloudflare_api_token = local.cloudflare_api_token
  zone_id              = local.zone_id
  firewall_rules = [
    {
      description = "Allow healthcheck from UptimeRobot IP addresses"
      expression  = "(http.request.method eq \"HEAD\" and ip.src in {${file("${path.root}/uptimerobot-ips.txt")}})"
      enable      = true
      action      = "skip",
      action_parameters = {
        ruleset = "current"
      }
      logging = {
        enabled = false
      }
    },
    {
      action      = "block"
      description = "Block requests originating from outside Vietnam"
      enabled     = true
      expression  = "(ip.src.country ne \"VN\")"
    },
    {
      action = "block"
      description = "Block external access to /admin Vaultwarden"
      enabled = true
      expression = "(http.request.full_uri eq \"https://bitwarden.datrollout.dev/admin\")"
    }
  ]
}