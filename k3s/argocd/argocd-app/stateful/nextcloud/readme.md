# Nextcloud Deployment via ArgoCD (Multi-Source)

This directory documents how Nextcloud is deployed in my homelab using ArgoCD with a multi-source approach, and why Nextcloud is chosen as a central hub for all cloud storage via rclone.

## Why Nextcloud?

- **Centralization**: Nextcloud acts as a unified interface for all my cloud storage providers (primarily Google Drive).
- **Federation**: Using rclone CSI, I can mount remote Google Drive accounts directly into Nextcloud, making files accessible and manageable from a single dashboard.
- **Self-Hosting**: Full control over data, privacy, and integrations.

## ArgoCD Multi-Source Manifest Strategy

Instead of a single Helm chart, I use ArgoCD’s multi-source feature to combine:

- **Helm Chart**: For the main Nextcloud deployment and configuration.
- **Raw Kubernetes Manifests**: For PersistentVolumes (PVs), PersistentVolumeClaims (PVCs), and SealedSecrets.
- **Custom Resources**: For rclone CSI volumes that mount external cloud storage.

This approach allows me to:

- **Decouple Storage and App Logic**: Storage volumes (local and remote) are managed independently from the Nextcloud app.
- **Automate Secrets Management**: Database and app credentials are handled securely via SealedSecrets.
- **Easily Extend Storage**: Add or remove cloud storage providers by updating rclone manifests, without touching the Nextcloud deployment.

## Directory Structure

```
.
├── argo-app.yaml            # ArgoCD Application manifest (multi-source)
├── helm/
│   └── values.yaml          # Nextcloud Helm values
├── raw-manifests/
│   ├── PVs.yaml             # PersistentVolumes (rclone CSI)
│   ├── PVCs.yaml            # PersistentVolumeClaims
│   ├── sealed-secret.yaml   # SealedSecrets for DB and app credentials
```

## Workflow

1. **Define Storage**: Create PVs/PVCs for each Google Drive account using rclone CSI.
2. **Secure Credentials**: Store DB/app secrets as SealedSecrets.
3. **Configure Nextcloud**: Set up Helm values for external storage and integrations.
4. **Deploy via ArgoCD**: The `argo-app.yaml` manifest references all sources, ensuring a consistent and automated rollout.

## Volumes Overview

| Volume Name         | Type                | Mount Path                | Durability      | Source/Sync Method           | Notes                                  |
|---------------------|---------------------|---------------------------|-----------------|------------------------------|----------------------------------------|
| nextcloud-data      | PVC (Longhorn)      | /var/www/html/data        | High            | Local PV                     | Backed up, critical user files         |
| shared-volume       | hostPath            | /shared-volume            | Low (can lose)  | Synced from external sources | Not backed up, easily re-synced        |
| aerith-gdrive       | PVC (rclone CSI)    | /cloud/aerith-gdrive      | External        | Google Drive via rclone      | Mounted, federated access              |
| karina-uit-gdrive   | PVC (rclone CSI)    | /cloud/karina-uit-gdrive    | External        | Google Drive via rclone      | Mounted, federated access              |
| kirara-gdrive       | PVC (rclone CSI)    | /cloud/kirara-gdrive      | External        | Google Drive via rclone      | Mounted, federated access              |
| sesshomaru-gdrive   | PVC (rclone CSI)    | /cloud/sesshomaru-gdrive  | External        | Google Drive via rclone      | Mounted, federated access              |

## Why Use `shared-volume`?

The `shared-volume` is a special persistent volume in my Nextcloud deployment designed for storing large, non-critical data. This volume is intentionally configured with less strict data durability because:

- **Data Can Be Lost**: I accept potential data loss on this volume since its contents (such as media files) can be easily re-synced or re-downloaded from external sources like torrents.
- **Efficient Storage**: By not prioritizing high availability or backup for `shared-volume`, I can optimize storage costs and performance for large files.
- **Sync Strategy**: Files in `shared-volume` are regularly synchronized from other sources, ensuring that any lost data can be restored automatically without manual intervention.

This approach allows Nextcloud to efficiently handle large, replaceable datasets while keeping critical data on more reliable volumes.

## Benefits

- **Scalable**: Add new cloud storage with minimal changes.
- **Maintainable**: Storage, secrets, and app logic are modular.
- **Automated**: ArgoCD keeps everything in sync and self-healing.

## References

- [ArgoCD Multi-Source Apps](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#multiple-source-apps)
- [Nextcloud Helm Chart](https://github.com/nextcloud/helm)
- [CSI Rclone Reloaded](https://github.com/dvcrn/csi-rclone-reloaded)