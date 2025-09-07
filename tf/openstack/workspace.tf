terraform {
  cloud {
    organization = "akira-homelab"
    workspaces {
      name = "uit"
    }
  }
}