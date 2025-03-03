terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
    }
  }
}

locals {
  cloudflare_api_token = var.cloudflare_api_token
  ddns_content = var.ddns_content
  zone_id = "0649c534ced1cb43ddc06d6a978b1dec"
  share_comment = "Managed by Terraform"
}

provider "cloudflare" {
  api_token = local.cloudflare_api_token
}

resource "cloudflare_dns_record" "gitlab_dnsRecord" {
  zone_id = local.zone_id
  comment = local.share_comment
  content = local.ddns_content
  name = "gitlab"
  proxied = true
  ttl = 1
  type = "CNAME"
}

resource "cloudflare_dns_record" "bitwarden_dnsRecord"{
  zone_id = local.zone_id
  comment = local.share_comment
  content = local.ddns_content
  name = "bitwarden"
  proxied = true
  ttl = 1
  type = "CNAME"
}

resource "cloudflare_dns_record" "duc_spring_dnsRecord"{
  zone_id = local.zone_id
  comment = local.share_comment
  content = local.ddns_content
  name = "duc-spring"
  proxied = false
  ttl = 1
  type = "CNAME"
}