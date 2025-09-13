#!/bin/bash

set -e

echo "🗑️  Deleting CloudNative-PG resources and CRDs..."

# Function to check if a resource exists
resource_exists() {
    kubectl get "$1" >/dev/null 2>&1
}

# Get all CRDs for postgresql.cnpg.io
echo "📋 Finding all postgresql.cnpg.io CRDs..."
CNPG_CRDS=$(kubectl get crd -o name | grep "postgresql.cnpg.io" | sed 's|customresourcedefinition.apiextensions.k8s.io/||')

if [ -z "$CNPG_CRDS" ]; then
    echo "✅ No postgresql.cnpg.io CRDs found!"
    exit 0
fi

echo "Found CRDs:"
for crd in $CNPG_CRDS; do
    echo "  - $crd"
done

# Delete all custom resources first
echo "📋 Deleting all postgresql.cnpg.io custom resources..."
for crd in $CNPG_CRDS; do
    if resource_exists "$crd"; then
        echo "  Deleting all $crd resources..."
        kubectl delete "$crd" --all --all-namespaces --timeout=60s || true
    fi
done

# Wait a moment for resources to be cleaned up
echo "⏳ Waiting for resources to be cleaned up..."
sleep 5

# Delete all postgresql.cnpg.io CRDs
echo "🔧 Deleting all postgresql.cnpg.io CRDs..."
for crd in $CNPG_CRDS; do
    if kubectl get crd "$crd" >/dev/null 2>&1; then
        echo "  Deleting CRD: $crd"
        kubectl delete crd "$crd" --timeout=60s
    else
        echo "  CRD not found: $crd"
    fi
done

# Alternative: Delete all by API group pattern
echo "🏷️  Attempting to delete any remaining postgresql.cnpg.io CRDs..."
kubectl delete crd -l app.kubernetes.io/name=cloudnative-pg --timeout=60s 2>/dev/null || true

echo "✅ CloudNative-PG cleanup completed!"

# Verify cleanup
echo "🔍 Verifying cleanup..."
remaining_crds=$(kubectl get crd | grep "postgresql.cnpg.io" || true)
if [ -z "$remaining_crds" ]; then
    echo "✅ All postgresql.cnpg.io CRDs have been successfully removed!"
else
    echo "⚠️  Some CRDs may still exist:"
    echo "$remaining_crds"
fi