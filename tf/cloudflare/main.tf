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
module "ddns_records"{
  source = "git::https://github.com/ngodat0103/terraform-module.git//cloudflare/dns-records"
  cloudflare_api_token = local.cloudflare_api_token
  zone_id = local.zone_id
  share_comment = local.share_comment
  ddns_content = var.ddns_content
  dns_records = {
    nextcloud = {
      type = "CNAME"
    }
    gitlab = {
      type = "CNAME"
    }
    bitwarden = {
      type = "CNAME"
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


#Need to import this resource from managed by cloudflare first
# Example: 
# terraform import cloudflare_ruleset.default zones/ab6606e8b3aad0b66008eb26f2dd3660/cfe2f8797a314e5ba48192a7e7520bd0
resource "cloudflare_ruleset" "default" {
  depends_on = [null_resource.download_uptimerobot_ips]
  kind       = "zone"
  name       = "default"
  phase      = "http_request_firewall_custom"
  zone_id    = local.zone_id
  rules = [
    {
      description = "Disable log request for gitlab-runenr"
      expression  = "(http.request.uri.path eq \"/api/v4/jobs/request\" and http.request.method eq \"POST\" and http.user_agent eq \"gitlab-runner 17.8.1 (17-8-stable; go1.23.2 X:cacheprog; linux/amd64)\" and ip.src eq 42.116.6.46)"
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
    }
  ]
}