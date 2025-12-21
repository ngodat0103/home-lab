terraform {
  cloud {
    organization = "akira-homelab"
    workspaces {
      name = "r2-cloudflare"
    }
  }
}