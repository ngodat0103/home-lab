locals {
  docker_containter_tag = ["production","web","docker_container"]
}
import {
  to = module.monitors_default.uptimerobot_monitor.default_monitor["vaultwarden"]
  id = "800604169"
}
import {
  to = module.monitors_default.uptimerobot_monitor.default_monitor["gitlab"]
  id = "800611041"
}
module "monitors_default" {
  source = "git::https://github.com/ngodat0103/terraform-module.git//uptimerobot/monitor?ref=0512fd63ac116bc291712abd03dd200bd71b8219"
  uptimerobot_api_key = var.uptimerobot_api_key
  monitors = {
    gitlab = {
      type = "HTTP"
      url = "https://gitlab.datrollout.dev/users/sign_in"
      tags = local.docker_containter_tag
    },
    vaultwarden = { 
      type = "HTTP"
      url = "https://bitwarden.datrollout.dev/alive"
      tags =  local.docker_containter_tag
    }
  }
}