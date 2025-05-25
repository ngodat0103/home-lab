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
  account_id = "4c8ad4e9fa8213af3fd284bb97b68b5e"
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



## Firewall


# Need to import this resource from managed by cloudflare first
## Example: 
## terraform import cloudflare_ruleset.default zones/0649c534ced1cb43ddc06d6a978b1dec/6580faae48cc4419bbd3fde67dc58d40
resource "cloudflare_ruleset" "default" {
  kind = "zone"
  name = "default"
  phase = "http_request_firewall_custom"
  zone_id = local.zone_id
  rules = [{
    action = "block"
    description = "Block when the SOURCE IP address is not in Vietnam"
    enabled = true
    expression = "(ip.src.country ne \"VN\")"
  }]
}