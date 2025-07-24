#!/bin/bash

## This script finds all PVCs related to Longhorn, scales down related deployments/replicasets,
## handles ArgoCD auto-heal settings, and verifies that Longhorn PVs are not in use

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found. Please install kubectl and ensure it's in your PATH."
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
}

# Function to disable ArgoCD auto-heal for all applications
disable_argocd_autoheal() {
    print_info "Checking for ArgoCD applications in argocd namespace..."
    
    if ! kubectl get namespace argocd &> /dev/null; then
        print_warning "ArgoCD namespace not found. Skipping ArgoCD auto-heal configuration."
        return 0
    fi
    
    local apps=$(kubectl get applications -n argocd -o name 2>/dev/null || true)
    
    if [[ -z "$apps" ]]; then
        print_warning "No ArgoCD applications found in argocd namespace."
        return 0
    fi
    
    print_info "Disabling auto-heal for ArgoCD applications..."
    
    while IFS= read -r app; do
        if [[ -n "$app" ]]; then
            local app_name=$(echo "$app" | cut -d'/' -f2)
            print_info "Disabling auto-heal for application: $app_name"
            
            kubectl patch "$app" -n argocd --type='merge' -p='{
                "spec": {
                    "syncPolicy": {
                        "automated": {
                            "selfHeal": false
                        }
                    }
                }
            }' 2>/dev/null || print_warning "Failed to disable auto-heal for $app_name"
        fi
    done <<< "$apps"
    
    print_success "ArgoCD auto-heal configuration completed."
    sleep 2
}

# Function to enable ArgoCD auto-heal for all applications
enable_argocd_autoheal() {
    print_info "Re-enabling ArgoCD auto-heal for applications..."
    
    if ! kubectl get namespace argocd &> /dev/null; then
        return 0
    fi
    
    local apps=$(kubectl get applications -n argocd -o name 2>/dev/null || true)
    
    while IFS= read -r app; do
        if [[ -n "$app" ]]; then
            local app_name=$(echo "$app" | cut -d'/' -f2)
            print_info "Re-enabling auto-heal for application: $app_name"
            
            kubectl patch "$app" -n argocd --type='merge' -p='{
                "spec": {
                    "syncPolicy": {
                        "automated": {
                            "selfHeal": true
                        }
                    }
                }
            }' 2>/dev/null || print_warning "Failed to re-enable auto-heal for $app_name"
        fi
    done <<< "$apps"
}

# Function to find workloads using a PVC
find_workloads_using_pvc() {
    local pvc_name="$1"
    local namespace="$2"
    local workloads=()
    
    # Skip kube-system namespace except for traefik (excluding svclb-traefik)
    if [[ "$namespace" == "kube-system" ]]; then
        print_info "Checking kube-system namespace - only processing Traefik workloads (excluding svclb-traefik)"
        
        # Only check for Traefik deployments in kube-system (excluding svclb-traefik)
        local traefik_deployments=$(kubectl get deployments -n "$namespace" -o json | jq -r --arg pvc "$pvc_name" '
            .items[] | select((.spec.template.spec.volumes[]?.persistentVolumeClaim.claimName == $pvc) and (.metadata.name | test("traefik"; "i")) and (.metadata.name | test("svclb-traefik"; "i") | not)) | .metadata.name
        ' 2>/dev/null || true)
        
        # Only check for Traefik statefulsets in kube-system (excluding svclb-traefik)
        local traefik_statefulsets=$(kubectl get statefulsets -n "$namespace" -o json | jq -r --arg pvc "$pvc_name" '
            .items[] | select(
                ((.spec.template.spec.volumes[]?.persistentVolumeClaim.claimName == $pvc) or 
                (.spec.volumeClaimTemplates[]?.metadata.name == $pvc or (.spec.volumeClaimTemplates[]?.metadata.name + "-" + .metadata.name + "-0") == $pvc)) and
                (.metadata.name | test("traefik"; "i")) and (.metadata.name | test("svclb-traefik"; "i") | not)
            ) | .metadata.name
        ' 2>/dev/null || true)
        
        # Only check for Traefik replicasets in kube-system (excluding svclb-traefik)
        local traefik_replicasets=$(kubectl get replicasets -n "$namespace" -o json | jq -r --arg pvc "$pvc_name" '
            .items[] | select((.spec.template.spec.volumes[]?.persistentVolumeClaim.claimName == $pvc) and (.metadata.name | test("traefik"; "i")) and (.metadata.name | test("svclb-traefik"; "i") | not)) | .metadata.name
        ' 2>/dev/null || true)
        
        # Add Traefik workloads to results
        [[ -n "$traefik_deployments" ]] && workloads+=("deployment:$traefik_deployments")
        [[ -n "$traefik_statefulsets" ]] && workloads+=("statefulset:$traefik_statefulsets")
        [[ -n "$traefik_replicasets" ]] && workloads+=("replicaset:$traefik_replicasets")
        
        # Skip DaemonSets entirely for kube-system
        printf '%s\n' "${workloads[@]}"
        return 0
    fi
    
    # For other namespaces, check all workloads except DaemonSets
    
    # Check Deployments
    local deployments=$(kubectl get deployments -n "$namespace" -o json | jq -r --arg pvc "$pvc_name" '
        .items[] | select(.spec.template.spec.volumes[]?.persistentVolumeClaim.claimName == $pvc) | .metadata.name
    ' 2>/dev/null || true)
    
    # Check StatefulSets
    local statefulsets=$(kubectl get statefulsets -n "$namespace" -o json | jq -r --arg pvc "$pvc_name" '
        .items[] | select(
            (.spec.template.spec.volumes[]?.persistentVolumeClaim.claimName == $pvc) or 
            (.spec.volumeClaimTemplates[]?.metadata.name == $pvc or (.spec.volumeClaimTemplates[]?.metadata.name + "-" + .metadata.name + "-0") == $pvc)
        ) | .metadata.name
    ' 2>/dev/null || true)
    
    # Check ReplicaSets
    local replicasets=$(kubectl get replicasets -n "$namespace" -o json | jq -r --arg pvc "$pvc_name" '
        .items[] | select(.spec.template.spec.volumes[]?.persistentVolumeClaim.claimName == $pvc) | .metadata.name
    ' 2>/dev/null || true)
    
    # Skip DaemonSets entirely - they should not be scaled down
    if [[ -z "$deployments" && -z "$statefulsets" && -z "$replicasets" ]]; then
        print_info "No workloads found using PVC $pvc_name - skipping DaemonSets as they cannot be safely scaled to 0"
    fi
    
    # Combine results (excluding DaemonSets)
    [[ -n "$deployments" ]] && workloads+=("deployment:$deployments")
    [[ -n "$statefulsets" ]] && workloads+=("statefulset:$statefulsets")
    [[ -n "$replicasets" ]] && workloads+=("replicaset:$replicasets")
    
    printf '%s\n' "${workloads[@]}"
}

# Function to scale down workloads
scale_down_workload() {
    local workload_type="$1"
    local workload_name="$2"
    local namespace="$3"
    
    print_info "Scaling down $workload_type/$workload_name in namespace $namespace"
    
    case "$workload_type" in
        "deployment")
            kubectl scale deployment "$workload_name" --replicas=0 -n "$namespace"
            ;;
        "statefulset")
            kubectl scale statefulset "$workload_name" --replicas=0 -n "$namespace"
            ;;
        "replicaset")
            kubectl scale replicaset "$workload_name" --replicas=0 -n "$namespace"
            ;;
        *)
            print_error "Unknown workload type: $workload_type"
            return 1
            ;;
    esac
}

# Function to wait for pods to terminate
wait_for_pods_termination() {
    local namespace="$1"
    local max_wait=300  # 5 minutes
    local wait_time=0
    
    print_info "Waiting for pods to terminate in namespace $namespace..."
    
    while [[ $wait_time -lt $max_wait ]]; do
        local running_pods
        
        if [[ "$namespace" == "kube-system" ]]; then
            # In kube-system, only count Traefik pods but exclude svclb-traefik pods
            running_pods=$(kubectl get pods -n "$namespace" --field-selector=status.phase=Running --no-headers 2>/dev/null | grep -i traefik | grep -v "svclb-traefik" | wc -l)
            print_info "Checking only Traefik pods in kube-system namespace (excluding svclb-traefik pods)..."
        else
            # In other namespaces, count all running pods
            running_pods=$(kubectl get pods -n "$namespace" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
        fi
        
        if [[ $running_pods -eq 0 ]]; then
            if [[ "$namespace" == "kube-system" ]]; then
                print_success "All relevant Traefik pods terminated in kube-system namespace (svclb-traefik pods ignored)"
            else
                print_success "All pods terminated in namespace $namespace"
            fi
            return 0
        fi
        
        if [[ "$namespace" == "kube-system" ]]; then
            print_info "Still waiting... ($running_pods Traefik pods running in kube-system, svclb-traefik pods ignored)"
        else
            print_info "Still waiting... ($running_pods pods running)"
        fi
        sleep 10
        wait_time=$((wait_time + 10))
    done
    
    if [[ "$namespace" == "kube-system" ]]; then
        print_warning "Timeout waiting for Traefik pods to terminate in kube-system namespace (svclb-traefik pods ignored)"
    else
        print_warning "Timeout waiting for pods to terminate in namespace $namespace"
    fi
    return 1
}

# Function to check if PV is in use
check_pv_usage() {
    local pv_name="$1"
    
    # Check if any pods are still using the PV
    local pods_using_pv=$(kubectl get pods --all-namespaces -o json | jq -r --arg pv "$pv_name" '
        .items[] | select(.spec.volumes[]?.persistentVolumeClaim.claimName as $pvc | 
        if $pvc then (kubectl get pvc $pvc -n .metadata.namespace -o json | jq -r .spec.volumeName) == $pv else false end) | 
        "\(.metadata.namespace)/\(.metadata.name)"
    ' 2>/dev/null || true)
    
    if [[ -n "$pods_using_pv" ]]; then
        return 1  # PV is still in use
    else
        return 0  # PV is not in use
    fi
}

# Main function
main() {
    print_info "Starting Longhorn PVC scaling script..."
    
    # Check prerequisites
    check_kubectl
    
    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        print_error "jq not found. Please install jq for JSON processing."
        exit 1
    fi
    
    # Disable ArgoCD auto-heal first
    disable_argocd_autoheal
    
    print_info "Finding all PVCs powered by Longhorn..."
    print_info "Note: Only workloads that use Longhorn PVCs will be scaled down"
    print_info "Note: DaemonSets will be ignored as they cannot be safely scaled to 0"
    print_info "Note: In kube-system namespace, only Traefik workloads will be processed (excluding svclb-traefik pods)"
    
    # Get all PVCs that use Longhorn storage class
    local longhorn_pvcs=$(kubectl get pvc --all-namespaces -o json | jq -r '
        .items[] | select(.spec.storageClassName == "longhorn" or .spec.storageClassName == "longhorn-static") | 
        "\(.metadata.namespace):\(.metadata.name)"
    ' 2>/dev/null || true)
    
    if [[ -z "$longhorn_pvcs" ]]; then
        print_warning "No Longhorn PVCs found in the cluster."
        enable_argocd_autoheal
        exit 0
    fi
    
    print_info "Found Longhorn PVCs:"
    echo "$longhorn_pvcs" | while IFS= read -r pvc_info; do
        echo "  - $pvc_info"
    done
    
    # Track scaled workloads for potential rollback
    declare -a scaled_workloads=()
    
    # Process each PVC
    while IFS=':' read -r namespace pvc_name; do
        if [[ -n "$namespace" && -n "$pvc_name" ]]; then
            print_info "Processing PVC: $pvc_name in namespace: $namespace"
            
            # Find workloads using this specific Longhorn PVC
            local workloads=$(find_workloads_using_pvc "$pvc_name" "$namespace")
            
            if [[ -z "$workloads" ]]; then
                print_info "No workloads found using Longhorn PVC $pvc_name - stateless workloads are not affected"
                continue
            fi
            
            print_info "Found workloads using Longhorn PVC $pvc_name - scaling them down to release storage"
            
            # Scale down each workload
            while IFS= read -r workload_info; do
                if [[ -n "$workload_info" ]]; then
                    local workload_type=$(echo "$workload_info" | cut -d':' -f1)
                    local workload_names=$(echo "$workload_info" | cut -d':' -f2-)
                    
                    # Handle multiple workloads of the same type
                    echo "$workload_names" | tr ' ' '\n' | while IFS= read -r workload_name; do
                        if [[ -n "$workload_name" ]]; then
                            if scale_down_workload "$workload_type" "$workload_name" "$namespace"; then
                                scaled_workloads+=("$workload_type:$workload_name:$namespace")
                                print_success "Scaled down $workload_type/$workload_name"
                            fi
                        fi
                    done
                fi
            done <<< "$workloads"
            
            # Wait for pods to terminate in this namespace
            wait_for_pods_termination "$namespace"
        fi
    done <<< "$longhorn_pvcs"
    
    print_info "Waiting additional 30 seconds for all resources to be fully released..."
    sleep 30
    
    # Verify PV usage status
    print_info "Checking Longhorn PV usage status..."
    
    local unused_pvs=()
    local still_in_use_pvs=()
    
    # Get all Longhorn PVs
    local longhorn_pvs=$(kubectl get pv -o json | jq -r '
        .items[] | select(.spec.storageClassName == "longhorn" or .spec.storageClassName == "longhorn-static") | 
        .metadata.name
    ' 2>/dev/null || true)
    
    while IFS= read -r pv_name; do
        if [[ -n "$pv_name" ]]; then
            local pv_status=$(kubectl get pv "$pv_name" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
            local bound_pvc=$(kubectl get pv "$pv_name" -o jsonpath='{.spec.claimRef.name}' 2>/dev/null || echo "")
            local bound_namespace=$(kubectl get pv "$pv_name" -o jsonpath='{.spec.claimRef.namespace}' 2>/dev/null || echo "")
            
            if [[ "$pv_status" == "Available" ]]; then
                unused_pvs+=("$pv_name (Status: Available)")
            elif [[ "$pv_status" == "Bound" && -n "$bound_pvc" ]]; then
                # Check if there are any pods using this PVC
                local pods_using_pvc=$(kubectl get pods -n "$bound_namespace" -o json 2>/dev/null | jq -r --arg pvc "$bound_pvc" '
                    .items[] | select(.spec.volumes[]?.persistentVolumeClaim.claimName == $pvc) | .metadata.name
                ' 2>/dev/null || true)
                
                if [[ -z "$pods_using_pvc" ]]; then
                    unused_pvs+=("$pv_name (PVC: $bound_namespace/$bound_pvc, Status: Bound but no pods using it)")
                else
                    still_in_use_pvs+=("$pv_name (PVC: $bound_namespace/$bound_pvc, Pods: $pods_using_pvc)")
                fi
            else
                still_in_use_pvs+=("$pv_name (Status: $pv_status)")
            fi
        fi
    done <<< "$longhorn_pvs"
    
    # Print results
    echo
    print_success "=== SCRIPT EXECUTION COMPLETED ==="
    echo
    
    if [[ ${#unused_pvs[@]} -gt 0 ]]; then
        print_success "Longhorn PVs that are NOT IN USE:"
        for pv in "${unused_pvs[@]}"; do
            echo -e "  ${GREEN}✓${NC} $pv"
        done
    else
        print_warning "No unused Longhorn PVs found."
    fi
    
    echo
    
    if [[ ${#still_in_use_pvs[@]} -gt 0 ]]; then
        print_warning "Longhorn PVs that are STILL IN USE:"
        for pv in "${still_in_use_pvs[@]}"; do
            echo -e "  ${YELLOW}⚠${NC} $pv"
        done
    fi
    
    echo
    print_info "Summary:"
    print_info "- Total Longhorn PVs checked: $(echo "$longhorn_pvs" | wc -l)"
    print_info "- PVs not in use: ${#unused_pvs[@]}"
    print_info "- PVs still in use: ${#still_in_use_pvs[@]}"
    
    # # Re-enable ArgoCD auto-heal
    # echo
    # enable_argocd_autoheal
    
    print_success "Script completed successfully!"
}

# Trap to ensure ArgoCD auto-heal is re-enabled on script exit
trap 'enable_argocd_autoheal' EXIT

# Run main function
main "$@"
