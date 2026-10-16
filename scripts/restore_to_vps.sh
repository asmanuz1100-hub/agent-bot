#!/usr/bin/env bash
set -euo pipefail

DUMP="${1:?Usage: bash scripts/restore_to_vps.sh backups/file.dump}"
test -f "$DUMP" || { echo "Dump not found: $DUMP" >&2; exit 1; }

docker compose ps db >/dev/null 2>&1 || {
  echo "docker compose database service is not available." >&2
  exit 1
}

echo "Restoring $DUMP into the local VPS PostgreSQL container..."
cat "$DUMP" | docker compose exec -T db sh -lc '
  export PGPASSWORD="$POSTGRES_PASSWORD"
  pg_restore \
    --clean \
    --if-exists \
    --no-owner \
    --no-acl \
    --exit-on-error \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB"
'

echo "Restore completed."
