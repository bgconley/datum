#!/usr/bin/env bash
# datum/scripts/restore-drill.sh
#
# Restore drill:
# - restores latest pg_dump into a temporary database
# - clones a project snapshot into a temp mountpoint when ZFS is available
# - runs reconciler + doctor against the restored cabinet tree

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUPS_ROOT="${DATUM_BACKUPS_ROOT:-/tank/datum/backups}"
RESTORE_DB="${DATUM_RESTORE_DB:-datum_restore_drill}"
RESTORE_ROOT="${DATUM_RESTORE_ROOT:-/tank/datum/restore-drill}"
PG_USER="${DATUM_DB_USER:-datum}"
PG_SERVICE="${DATUM_DB_SERVICE:-paradedb}"
PG_SYSTEM_DB="${DATUM_DB_SYSTEM_DB:-postgres}"

LATEST_DUMP="$(ls -1t "$BACKUPS_ROOT"/pgdump/operational-*.sql.gz 2>/dev/null | head -n 1 || true)"
if [ -z "$LATEST_DUMP" ]; then
    echo "FATAL: no pg_dump exports found under $BACKUPS_ROOT/pgdump"
    exit 1
fi

run() {
    echo "+ $*"
    "$@"
}

reconcile_and_doctor() {
    local restore_path="$1"
    local venv_path="${DATUM_VENV_PATH:-/tank/venvs/datum}"
    if [ ! -f "$venv_path/bin/activate" ]; then
        echo "FATAL: Datum venv not found at $venv_path"
        exit 1
    fi

    # shellcheck disable=SC1090
    source "$venv_path/bin/activate"
    python - <<PY
import asyncio
from pathlib import Path
from datum.services.reconciler import reconcile_project
from datum.services.doctor import check_project

project_path = Path(${restore_path@Q})
asyncio.run(reconcile_project(project_path))
report = check_project(project_path)
if not report.is_healthy:
    raise SystemExit("\\n".join(report.errors))
print("doctor=healthy")
PY
}

clone_latest_snapshot() {
    local dataset="$1"
    local mountpoint="$2"
    if ! command -v zfs >/dev/null 2>&1; then
        echo "WARN: zfs unavailable; skipping dataset clone for $dataset"
        return 0
    fi
    local snapshot
    snapshot="$(zfs list -H -o name -t snapshot -r "$dataset" | tail -n 1 || true)"
    if [ -z "$snapshot" ]; then
        echo "WARN: no snapshot found for $dataset"
        return 0
    fi
    run zfs destroy -r "${dataset}_restore" >/dev/null 2>&1 || true
    run zfs clone -o mountpoint="$mountpoint" "$snapshot" "${dataset}_restore"
}

echo "=== Datum restore drill ==="
echo "Repo: $REPO_DIR"
echo "Latest dump: $LATEST_DUMP"
echo "Restore DB: $RESTORE_DB"
echo "Restore root: $RESTORE_ROOT"

mkdir -p "$RESTORE_ROOT"

run docker compose -f "$REPO_DIR/docker-compose.yml" exec -T "$PG_SERVICE" \
    psql -U "$PG_USER" -d "$PG_SYSTEM_DB" -c "DROP DATABASE IF EXISTS ${RESTORE_DB};"
run docker compose -f "$REPO_DIR/docker-compose.yml" exec -T "$PG_SERVICE" \
    psql -U "$PG_USER" -d "$PG_SYSTEM_DB" -c "CREATE DATABASE ${RESTORE_DB};"
gzip -dc "$LATEST_DUMP" \
    | docker compose -f "$REPO_DIR/docker-compose.yml" exec -T "$PG_SERVICE" \
        psql -U "$PG_USER" -d "$RESTORE_DB"

clone_latest_snapshot "tank/datum/projects" "$RESTORE_ROOT/projects"

if [ -d "$RESTORE_ROOT/projects" ]; then
    mapfile -t restored_projects < <(
        find "$RESTORE_ROOT/projects" -mindepth 1 -maxdepth 1 -type d | sort
    )
    if [ "${#restored_projects[@]}" -eq 0 ]; then
        echo "WARN: no restored projects found under $RESTORE_ROOT/projects"
    else
        for project_path in "${restored_projects[@]}"; do
            echo "Validating restored project: $project_path"
            reconcile_and_doctor "$project_path"
        done
    fi
fi

echo "Restore drill completed successfully."
