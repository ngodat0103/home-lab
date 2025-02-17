terraform { 
  cloud { 
    organization = "akira-homelab" 
    workspaces { 
      name = "dns-workspace-cli" 
    } 
  } 
}