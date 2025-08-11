locals {
  web_tag               = ["production", "web"]
  docker_containter_tag = concat(local.web_tag, ["docker_container"])
  snap_tag              = concat(local.web_tag, ["snap"])
}
import {
  to = module.monitors_default.uptimerobot_monitor.default_monitor["vaultwarden"]
  id = "800604169"
}
import {
  to = module.monitors_default.uptimerobot_monitor.default_monitor["gitlab"]
  id = "800611041"
}

import {
  to = module.monitors_default.uptimerobot_monitor.default_monitor["nextcloud"]
  id = "800604827"
}
module "monitors_default" {
  #human browserable: https://github.com/ngodat0103/terraform-module/tree/4ed41c0f40071a1127c33526e1dc368b6f3edd50
  source              = "git::https://github.com/ngodat0103/terraform-module.git//uptimerobot/monitor?ref=4ed41c0f40071a1127c33526e1dc368b6f3edd50"
  uptimerobot_api_key = var.uptimerobot_api_key
  monitors = {
    gitlab = {
      type = "HTTP"
      url  = "https://gitlab.datrollout.dev/users/sign_in"
      tags = local.docker_containter_tag
    },
    vaultwarden = {
      type = "HTTP"
      url  = "https://bitwarden.datrollout.dev/alive"
      tags = local.docker_containter_tag
    },
    nextcloud = {
      type = "HTTP"
      url  = "https://nextcloud.datrollout.dev/index.php/login"
      tags = local.snap_tag
    }
  }
}