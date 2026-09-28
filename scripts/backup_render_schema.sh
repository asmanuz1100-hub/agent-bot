#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${SOURCE_DATABASE_URL:?Set SOURCE_DATABASE_URL to the current Render PostgreSQL connection URL}"
DB_SCHEMA="${DB_SCHEMA:-agentbot}"
OUT="${1:-backups/render-${DB_SCHEMA}-$(date -u +%Y%m%dT%H%M%SZ).dump}"

command -v pg_dump >/dev/null 2>&1 || {
  echo "pg_dump is required. Install postgresql-client first." >&2
  exit 1
}
command -v pg_restore >/dev/null 2>&1 || {
  echo "pg_restore is required. Install postgresql-client first." >&2
  exit 1
}

mkdir -p "$(dirname "$OUT")"

echo "Backing up PostgreSQL schema '$DB_SCHEMA'..."
pg_dump "$SOURCE_DATABASE_URL" \
  --format=custom \
  --schema="$DB_SCHEMA" \
  --no-owner \
  --no-acl \
  --file="$OUT"

# Verify that the custom-format archive is readable before it is trusted.
pg_restore --list "$OUT" >/dev/null

echo "Backup verified: $OUT"
