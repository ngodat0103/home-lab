#!/bin/bash
set -euo pipefail
check_disk_rclone() {
   rclone about $1: --json | jq '.free/(1024*1024*1024)'
}

run_restic_backup(){
export PATH=$PATH:/usr/bin/rclone
export RESTIC_REPOSITORY=rclone:aerith-gdrive:/restic
export RESTIC_PASSWORD_FILE=/root/restic/password.txt
restic backup /mnt/recovery/cloud
}
free_bytes=$(check_disk_rclone $1)
if (( $(echo "$free_bytes <=2" | bc -l) )); then
    echo "Low space ($free_bytes GB), abort backup, need at least 2gb to operate"
    exit 1 
else
    echo "Remote free space is $free_bytes GB, proceed backup"
    run_restic_backup
fi