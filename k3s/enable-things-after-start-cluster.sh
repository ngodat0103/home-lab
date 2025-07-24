#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}
print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}
print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

if ! command -v kubectl &> /dev/null; then
    echo "[ERROR] kubectl not found."
    exit 1
fi

if ! kubectl get namespace argocd &> /dev/null; then
    print_warning "ArgoCD namespace not found."
    exit 0
fi

apps=$(kubectl get applications -n argocd -o name 2>/dev/null || true)

if [[ -z "$apps" ]]; then
    print_warning "No ArgoCD applications found."
    exit 0
fi

print_info "Enabling auto-sync and self-heal for all ArgoCD applications..."

while IFS= read -r app; do
    if [[ -n "$app" ]]; then
        app_name=$(echo "$app" | cut -d'/' -f2)
        print_info "Enabling auto-sync for: $app_name"
        kubectl patch "$app" -n argocd --type='merge' -p='{
            "spec": {
                "syncPolicy": {
                    "automated": {
                        "prune": true,
                        "selfHeal": true
                    }
                }
            }
        }' 2>/dev/null || print_warning "Failed to enable auto-sync for $app_name"
    fi
done <<< "$apps"

print_success "Auto-sync enabled for all ArgoCD applications."

print_info "Scaling Traefik deployment in kube-system namespace to 1 replicas"
kubectl scale deployment traefik -n kube-system --replicas=1 2> /dev/null \
 && print_success "Traefik deployment scaled to 1 replica" \
 || print_warning "Failed to scale traefik deployment"