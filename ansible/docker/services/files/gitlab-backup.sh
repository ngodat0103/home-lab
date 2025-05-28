#!/bin/bash
cd /mnt/data2/gitlab
docker exec gitlab gitlab-backup create
mkdir -p /mnt/cloud/gitlab
rsync -aP backups/ /mnt/cloud/gitlab/