#!/bin/bash
# Daily logical backup of the Syndra database, as installed on the VPS at
# ~/backup_syndra.sh and run by infra/backup.cron. deploy.sh does not copy
# this file: a change here has to be applied on the VPS by hand.
#
# The dump stays on the VPS disk, so it covers mistakes and corruption in the
# database, not the loss of the server itself.
DATE=$(date +%Y%m%d_%H%M%S)
docker exec syndra_postgres pg_dump -U syndra_user syndra_db | gzip > ~/backups/syndra_$DATE.sql.gz
# Seven days of dumps: enough to go back past a bad week, small enough for the disk.
find ~/backups -name "*.sql.gz" -mtime +7 -delete
