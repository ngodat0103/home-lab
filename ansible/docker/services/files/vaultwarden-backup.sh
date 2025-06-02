#!/bin/bash
cd ~
pg_dump > data-backup.sql
tar -cf vaultwarden-backup-latest.tar .
mv vaultwarden-backup-latest.tar /mnt/cloud/
chmod 600 /mnt/recovery/cloud/vaultwarden-backup-latest.tar