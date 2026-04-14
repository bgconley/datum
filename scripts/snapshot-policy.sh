#!/usr/bin/env bash
# datum/scripts/snapshot-policy.sh
#
# Apply the Datum ZFS snapshot policy tier:
#   frequent | daily | weekly | monthly

set -euo pipefail

TIER="${1:-daily}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

case "$TIER" in
    frequent)
        DATASETS=("tank/datum/projects")
        KEEP=96
        ;;
    daily)
        DATASETS=("tank/datum/projects" "tank/datum/postgres" "tank/datum/postgres-wal" "tank/datum/blobs")
        KEEP=30
        ;;
    weekly)
        DATASETS=("tank/datum/projects" "tank/datum/postgres" "tank/datum/postgres-wal" "tank/datum/blobs")
        KEEP=12
        ;;
    monthly)
        DATASETS=("tank/datum/projects")
        KEEP=12
        ;;
    *)
        echo "Usage: $0 [frequent|daily|weekly|monthly]"
        exit 1
        ;;
esac

if ! command -v zfs >/dev/null 2>&1; then
    echo "FATAL: zfs command not found"
    exit 1
fi

for dataset in "${DATASETS[@]}"; do
    snapshot="${dataset}@${TIER}-${STAMP}"
    echo "+ zfs snapshot $snapshot"
    zfs snapshot "$snapshot"

    mapfile -t old_snapshots < <(zfs list -H -o name -t snapshot -r "$dataset" | grep "@${TIER}-" | sort)
    if [ "${#old_snapshots[@]}" -le "$KEEP" ]; then
        continue
    fi

    prune_count=$((${#old_snapshots[@]} - KEEP))
    for snapshot_name in "${old_snapshots[@]:0:prune_count}"; do
        echo "+ zfs destroy $snapshot_name"
        zfs destroy "$snapshot_name"
    done
done

echo "Snapshot policy complete for tier=$TIER"
