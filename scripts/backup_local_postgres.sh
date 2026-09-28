#!/usr/bin/env bash
set -euo pipefail
umask 077

OUT_DIR="${BACKUP_DIR:-backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/vps-agentbot-$(date -u +%Y%m%dT%H%M%SZ).dump"

echo "Creating local PostgreSQL backup..."
docker compose exec -T db sh -lc '
  export PGPASSWORD="$POSTGRES_PASSWORD"
  pg_dump \
    --format=custom \
    --schema="$DB_SCHEMA" \
    --no-owner \
    --no-acl \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB"
' > "$OUT"

test -s "$OUT" || { echo "Backup is empty: $OUT" >&2; exit 1; }
find "$OUT_DIR" -type f -name 'vps-agentbot-*.dump' -mtime "+$KEEP_DAYS" -delete

echo "Backup created: $OUT"
