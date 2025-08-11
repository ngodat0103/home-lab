terraform {
  cloud {

    organization = "akira-homelab"

    workspaces {
      name = "uptimerobot"
    }
  }
}