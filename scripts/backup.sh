#!/usr/bin/env bash
# datum/scripts/backup.sh
#
# Daily operational backup:
# - pg_dump for operational/non-rebuildable tables
# - ZFS snapshots for cabinet datasets
# - retention pruning for exported dumps

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

BACKUPS_ROOT="${DATUM_BACKUPS_ROOT:-/tank/datum/backups}"
PG_USER="${DATUM_DB_USER:-datum}"
PG_DB="${DATUM_DB_NAME:-datum}"
PG_SERVICE="${DATUM_DB_SERVICE:-paradedb}"
RETENTION_DAYS="${DATUM_BACKUP_RETENTION_DAYS:-30}"
SNAPSHOT_LABEL="${DATUM_BACKUP_SNAPSHOT_LABEL:-daily}"

mkdir -p "$BACKUPS_ROOT/pgdump"

run() {
    echo "+ $*"
    "$@"
}

snapshot_dataset() {
    local dataset="$1"
    local name="${dataset}@${SNAPSHOT_LABEL}-${STAMP}"
    if command -v zfs >/dev/null 2>&1; then
        run zfs snapshot "$name"
    else
        echo "WARN: zfs unavailable; skipping snapshot for $dataset"
    fi
}

prune_exports() {
    find "$BACKUPS_ROOT/pgdump" -type f -name '*.sql.gz' -mtime +"$RETENTION_DAYS" -print -delete 2>/dev/null || true
}

echo "=== Datum backup ==="
echo "Repo: $REPO_DIR"
echo "Backups: $BACKUPS_ROOT"
echo "Timestamp: $STAMP"

if [ -f "$REPO_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$REPO_DIR/.env"
    set +a
fi

run docker compose -f "$REPO_DIR/docker-compose.yml" exec -T "$PG_SERVICE" \
    pg_dump -U "$PG_USER" -d "$PG_DB" --no-owner --no-privileges \
    | gzip -c > "$BACKUPS_ROOT/pgdump/operational-${STAMP}.sql.gz"

snapshot_dataset "tank/datum/projects"
snapshot_dataset "tank/datum/postgres"
snapshot_dataset "tank/datum/postgres-wal"
snapshot_dataset "tank/datum/blobs"

prune_exports

echo "Backup complete: $BACKUPS_ROOT/pgdump/operational-${STAMP}.sql.gz"
