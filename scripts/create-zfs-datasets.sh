#!/usr/bin/env bash
# datum/scripts/create-zfs-datasets.sh
#
# Creates all ZFS datasets for Datum on the GPU node.
# Run once during initial setup. Requires sudo.
# Usage: sudo bash scripts/create-zfs-datasets.sh

set -euo pipefail

echo "=== Creating Datum ZFS datasets ==="

# Parent dataset
zfs create -o mountpoint=none tank/datum 2>/dev/null || echo "tank/datum already exists"

# Repos (for git clones on GPU node)
zfs create \
    -o mountpoint=/tank/repos \
    -o recordsize=32K \
    -o compression=zstd \
    -o atime=off \
    tank/repos 2>/dev/null || echo "tank/repos already exists"

# The Cabinet — canonical source of truth
zfs create \
    -o mountpoint=/tank/datum/projects \
    -o recordsize=128K \
    -o compression=zstd \
    -o atime=off \
    -o xattr=sa \
    -o snapdir=visible \
    tank/datum/projects 2>/dev/null || echo "tank/datum/projects already exists"

# Postgres data
zfs create \
    -o mountpoint=/tank/datum/pgdata \
    -o recordsize=8K \
    -o compression=lz4 \
    -o primarycache=all \
    -o atime=off \
    -o logbias=latency \
    -o redundant_metadata=most \
    tank/datum/postgres 2>/dev/null || echo "tank/datum/postgres already exists"

# Postgres WAL (separate for performance)
zfs create \
    -o mountpoint=/tank/datum/pgwal \
    -o recordsize=128K \
    -o compression=lz4 \
    -o logbias=throughput \
    -o primarycache=metadata \
    -o atime=off \
    tank/datum/postgres-wal 2>/dev/null || echo "tank/datum/postgres-wal already exists"

# Content-addressed blob store
zfs create \
    -o mountpoint=/tank/datum/blobs \
    -o recordsize=1M \
    -o compression=zstd \
    -o atime=off \
    tank/datum/blobs 2>/dev/null || echo "tank/datum/blobs already exists"

# Derived/rebuildable cache
zfs create \
    -o mountpoint=/tank/datum/cache \
    -o recordsize=128K \
    -o compression=zstd \
    -o sync=disabled \
    -o atime=off \
    tank/datum/cache 2>/dev/null || echo "tank/datum/cache already exists"

# Backup staging
zfs create \
    -o mountpoint=/tank/datum/backups \
    -o recordsize=1M \
    -o compression=zstd \
    -o atime=off \
    tank/datum/backups 2>/dev/null || echo "tank/datum/backups already exists"

echo ""
echo "=== Dataset status ==="
zfs list -o name,mountpoint,recordsize,compression,sync -r tank/datum tank/repos

echo ""
echo "=== Done. Next steps: ==="
echo "1. Clone datum repo: cd /tank/repos && git clone https://github.com/bgconley/datum.git"
echo "2. Set ownership: sudo chown -R $(whoami):$(whoami) /tank/datum/projects /tank/datum/blobs /tank/datum/cache /tank/datum/backups"
