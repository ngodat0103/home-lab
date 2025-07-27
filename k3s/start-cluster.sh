#!/bin/bash
source <(curl -fsSL https://raw.githubusercontent.com/ngodat0103/common-stuff/refs/heads/main/0-shell/9-argocd/argocd.sh)
vagrant up

# Post start
enable_argocd_self_heal