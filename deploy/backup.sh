#!/bin/sh
# Sauvegarde PostgreSQL quotidienne (pg_dump compressé), rétention BACKUP_RETENTION_DAYS jours.
# Restauration : gunzip -c backups/orbit-AAAAMMJJ-HHMM.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U $POSTGRES_USER $POSTGRES_DB
set -eu
while true; do
  file="/backups/orbit-$(date +%Y%m%d-%H%M).sql.gz"
  if pg_dump --no-owner --clean --if-exists | gzip > "$file.tmp"; then
    mv "$file.tmp" "$file"
    echo "Sauvegarde OK : $file"
  else
    rm -f "$file.tmp"
    echo "ÉCHEC de la sauvegarde" >&2
  fi
  find /backups -name 'orbit-*.sql.gz' -mtime "+${BACKUP_RETENTION_DAYS}" -delete
  sleep 86400
done
