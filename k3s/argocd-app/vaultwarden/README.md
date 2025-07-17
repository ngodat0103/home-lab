# Vaultwarden ArgoCD Application

This directory contains the configuration files for deploying and managing Vaultwarden (a lightweight Bitwarden server implementation) using ArgoCD in a Kubernetes cluster.

## Overview

Vaultwarden is deployed as an ArgoCD application that provides:
- Password management server compatible with Bitwarden clients
- PostgreSQL database backend
- Automated backup system to Google Drive
- TLS-enabled ingress with Let's Encrypt certificates
- Traefik ingress controller integration

## Files

### Core Configuration

- **`argo-app.yaml`** - ArgoCD Application manifest that defines the deployment
- **`values.yaml`** - Helm chart values for customizing the Vaultwarden deployment
- **`.gitignore`** - Git ignore rules for the directory

### Backup System

- **`backup-cronjob.yaml`** - CronJob for scheduled database backups to Google Drive
- **`job.yaml`** - One-time backup job for manual backup execution

## Configuration Details

### Application Settings

- **Namespace**: `vaultwarden`
- **Domain**: `bitwarden.ngodat0103.live`
- **Helm Chart**: `vaultwarden` from `https://guerzon.github.io/vaultwarden`
- **Chart Version**: `0.32.1`
- **Vaultwarden Version**: `1.33.2-alpine`

### Database Configuration

- **Type**: PostgreSQL
- **Host**: `postgresql-rw.database`
- **Port**: `5432`
- **Database Name**: `vaultwarden`
- **Connection Pool**: 10 connections
- **Connection Retries**: 15
- **Credentials**: Stored in `vaultwarden-secret` Kubernetes secret

### Ingress Configuration

- **Ingress Controller**: Traefik
- **TLS**: Enabled with Let's Encrypt certificates
- **Hostname**: `bitwarden.ngodat0103.live`
- **Path**: `/` (root path)
- **Path Type**: Prefix

### Security Features

- **User Registration**: Enabled with email verification
- **Domain Restrictions**: Not configured (open registration)
- **Organization Events**: Disabled
- **Sends**: Enabled (allows sharing of text/files)
- **Attachment Limits**: Not configured
- **Trash Auto-Delete**: Not configured

### Backup System

The backup system consists of two main components:

#### Scheduled Backup (CronJob)
- **Schedule**: Daily at 1:30 AM Vietnam time (`30 1 * * *`)
- **Timezone**: `Asia/Ho_Chi_Minh`
- **Backup Process**:
  1. Database dump using `pg_dump` from PostgreSQL 16.9
  2. Backup to Google Drive using Restic with rclone
- **Storage**: Temporary in-memory storage (50Mi)
- **Security**: Runs as non-root user (UID/GID: 1012)

#### Manual Backup (Job)
- One-time execution version of the backup process
- Same configuration as the CronJob
- Useful for immediate backups before maintenance

#### Backup Configuration
- **Restic Repository**: `rclone:aerith-google-drive:/restic/k8s/vaultwarden`
- **Storage Backend**: Google Drive via rclone
- **Credentials**: Stored in `restic-secret` Kubernetes secret
- **Database Connection**: Uses read-replica `postgresql-r.database`

## Deployment

### Prerequisites

1. ArgoCD installed and configured
2. PostgreSQL database with:
   - Database named `vaultwarden`
   - User with appropriate permissions
   - Read-write service at `postgresql-rw.database`
   - Read-only service at `postgresql-r.database`
3. Kubernetes secrets:
   - `vaultwarden-secret` containing database credentials and configuration
   - `restic-secret` containing backup credentials and rclone configuration
4. Traefik ingress controller configured with Let's Encrypt

### Applying the Configuration

The application is deployed via ArgoCD using the configuration in `argo-app.yaml`. ArgoCD will:
1. Deploy the Vaultwarden Helm chart using the customized values
2. Create the necessary Kubernetes resources
3. Set up ingress with TLS certificates
4. Deploy the backup CronJob

### Manual Deployment Commands

If deploying manually without ArgoCD:

```bash
# Apply the backup CronJob
kubectl apply -f backup-cronjob.yaml

# Run a manual backup (optional)
kubectl apply -f job.yaml

# Deploy using Helm (with appropriate values)
helm repo add vaultwarden https://guerzon.github.io/vaultwarden
helm install vaultwarden vaultwarden/vaultwarden -f values.yaml -n vaultwarden
```

## Monitoring and Maintenance

### Backup Monitoring

Check backup job status:
```bash
# Check CronJob status
kubectl get cronjob aerith-do-backup-vaultwarden -n vaultwarden

# Check recent backup job executions
kubectl get jobs -n vaultwarden | grep backup

# Check backup job logs
kubectl logs -l job-name=aerith-do-backup-vaultwarden -n vaultwarden
```

### Application Monitoring

Monitor the application:
```bash
# Check pod status
kubectl get pods -n vaultwarden

# Check ingress status
kubectl get ingress -n vaultwarden

# Check service status
kubectl get svc -n vaultwarden
```

### Database Connection

Verify database connectivity:
```bash
# Check if database is accessible
kubectl exec -it deployment/vaultwarden -n vaultwarden -- nc -zv postgresql-rw.database 5432
```

## Troubleshooting

### Common Issues

1. **Database Connection Failures**
   - Verify `vaultwarden-secret` contains correct `DATABASE_URL`
   - Check PostgreSQL service availability
   - Verify database permissions

2. **Backup Failures**
   - Check `restic-secret` contains valid rclone configuration
   - Verify Google Drive access permissions
   - Check backup job logs for specific errors

3. **TLS Certificate Issues**
   - Verify Traefik is configured with Let's Encrypt
   - Check DNS resolution for the domain
   - Review Traefik logs for certificate provisioning

4. **Login Issues**
   - Check if user registration is enabled
   - Verify email verification settings
   - Check domain restrictions

### Logs

Access application logs:
```bash
# Vaultwarden application logs
kubectl logs deployment/vaultwarden -n vaultwarden

# Backup job logs
kubectl logs jobs/aerith-do-backup-vaultwarden -n vaultwarden
```

## Security Considerations

- Database credentials are stored in Kubernetes secrets
- Application runs with appropriate security contexts
- TLS is enforced for all web traffic
- Regular automated backups protect against data loss
- User registration requires email verification
- Consider implementing domain restrictions for user registration in production

## Customization

To customize the deployment:

1. Modify `values.yaml` with your specific configuration
2. Update domain names in both `values.yaml` and `argo-app.yaml`
3. Adjust backup schedule in `backup-cronjob.yaml` if needed
4. Configure additional security settings as required

For available configuration options, refer to the [Vaultwarden Helm chart documentation](https://github.com/guerzon/vaultwarden/tree/main/charts/vaultwarden).