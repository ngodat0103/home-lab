#!/bin/bash
export PATH=$PATH:/usr/bin/rclone
export RESTIC_REPOSITORY=rclone:aerith-google-drive:/restic
export RESTIC_PASSWORD_FILE=/root/restic/password.txt
restic backup /mnt/recovery/cloud