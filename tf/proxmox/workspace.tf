terraform {
  cloud {

    organization = "akira-homelab"

    workspaces {
      name = "production"
    }
  }
}