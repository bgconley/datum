#!/usr/bin/env bash
# datum/scripts/integration-test.sh
#
# Canonical verification script for the GPU node.
# Tests the FULL stack: ZFS datasets, ParadeDB, migrations, unit tests,
# filesystem write paths, API endpoints, watcher, frontend, and Caddy.
#
# Prerequisites:
#   - ZFS datasets created (scripts/create-zfs-datasets.sh)
#   - Datum venv bootstrapped (scripts/bootstrap-gpu-node.sh)
#
# Usage: bash scripts/integration-test.sh

set -euo pipefail

# --- Configuration ---
VENV_PATH="/tank/venvs/datum"
export DATUM_PROJECTS_ROOT="${DATUM_PROJECTS_ROOT:-/tank/datum/projects}"
export DATUM_PGDATA="${DATUM_PGDATA:-/tank/datum/pgdata}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
API_TEST_SLUG="api-test"

cleanup_api_test_state() {
    local slug="${1:-$API_TEST_SLUG}"
    local quiet="${2:-0}"

    if [ "$quiet" != "1" ]; then
        echo "  Cleaning previous test data..."
    fi

    (
        cd "$REPO_DIR"
        docker compose exec -T paradedb psql -v ON_ERROR_STOP=1 -q -U datum -d datum >/dev/null <<SQL
DELETE FROM version_head_events
WHERE project_id IN (SELECT id FROM projects WHERE slug = '${slug}')
   OR document_id IN (
       SELECT id FROM documents
       WHERE project_id IN (SELECT id FROM projects WHERE slug = '${slug}')
   );
DELETE FROM audit_events
WHERE project_id IN (SELECT id FROM projects WHERE slug = '${slug}');
DELETE FROM document_versions
WHERE document_id IN (
    SELECT id FROM documents
    WHERE project_id IN (SELECT id FROM projects WHERE slug = '${slug}')
);
DELETE FROM source_files
WHERE project_id IN (SELECT id FROM projects WHERE slug = '${slug}');
DELETE FROM documents
WHERE project_id IN (SELECT id FROM projects WHERE slug = '${slug}');
DELETE FROM projects
WHERE slug = '${slug}';
SQL
    )

    rm -rf "${DATUM_PROJECTS_ROOT}/${slug}" 2>/dev/null || true

    if [ "$quiet" != "1" ]; then
        echo "    OK"
    fi
}

trap 'cleanup_api_test_state "$API_TEST_SLUG" 1 || true' EXIT

echo "=== Datum Full-Stack Integration Tests ==="
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "Venv: $VENV_PATH"
echo "Projects root: $DATUM_PROJECTS_ROOT"
echo "PG data: $DATUM_PGDATA"
echo ""

# --- 0. Verify datum venv exists ---
echo "--- 0. Datum venv ---"
if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "  FATAL: Datum venv not found at $VENV_PATH"
    echo "  Run: bash scripts/bootstrap-gpu-node.sh"
    exit 1
fi
source "$VENV_PATH/bin/activate"
echo "  Python: $(python --version)"
echo "  datum installed: $(pip show datum 2>/dev/null | grep Version || echo 'NOT FOUND')"
echo ""

# --- 1. Verify ZFS datasets exist ---
echo "--- 1. ZFS Datasets ---"
for ds in tank/datum/projects tank/datum/postgres tank/datum/postgres-wal tank/datum/blobs tank/datum/cache; do
    if zfs list "$ds" &>/dev/null; then
        echo "  OK: $ds"
    else
        echo "  MISSING: $ds"
        echo "  Run: sudo bash scripts/create-zfs-datasets.sh"
        exit 1
    fi
done
echo ""

# --- 2. Build and start ALL services ---
echo "--- 2. Starting services ---"
cd "$REPO_DIR"
docker compose down --remove-orphans 2>/dev/null || true
docker compose build --quiet
docker compose up -d
echo "Waiting for services to be ready..."
sleep 10

# Verify each service is up
echo "  ParadeDB:"
docker compose exec -T paradedb pg_isready -U datum && echo "    OK" || { echo "    FAIL"; exit 1; }
echo "  datum-api:"
curl -sf http://localhost:8001/api/v1/health | grep -q ok && echo "    OK" || { echo "    FAIL"; exit 1; }
echo "  datum-frontend (via Caddy :3080):"
curl -sf http://localhost:3080/ | grep -q Datum && echo "    OK" || { echo "    FAIL"; exit 1; }
echo ""

# --- 3. Migrations ---
echo "--- 3. Migrations ---"
cd "$BACKEND_DIR"
DATUM_DATABASE_URL="postgresql+asyncpg://datum:${DATUM_DB_PASSWORD:-datum_dev}@localhost:5432/datum" \
    alembic upgrade head
echo "  OK"
cd "$REPO_DIR"
echo ""

# --- 4. Unit tests ---
echo "--- 4. Unit tests ---"
cd "$BACKEND_DIR"
DATUM_DATABASE_URL="postgresql+asyncpg://datum:${DATUM_DB_PASSWORD:-datum_dev}@localhost:5432/datum" \
    pytest tests/ -v --tb=short
cd "$REPO_DIR"
echo ""

# --- 5. Filesystem integration (direct service calls against real ZFS) ---
echo "--- 5. Filesystem integration ---"
cd "$BACKEND_DIR"
DATUM_PROJECTS_ROOT="$DATUM_PROJECTS_ROOT" python -c "
from pathlib import Path
from datum.services.project_manager import create_project
from datum.services.document_manager import create_document, save_document
from datum.services.reconciler import reconcile_project
from datum.services.doctor import check_project
from datum.services.filesystem import compute_content_hash
from datum.config import settings
import asyncio

root = settings.projects_root
root.mkdir(parents=True, exist_ok=True)

p = create_project(root, 'Integration Test', 'integration-test')
project_path = root / 'integration-test'
print(f'  Created project: {p.slug}')

# Verify project.yaml versioned
assert (project_path / '.piq' / 'project' / 'versions' / 'v001.yaml').exists()
print('  project.yaml v001 exists: OK')

d = create_document(project_path, 'docs/test.md', 'Test Doc', 'plan', '# Test')
print(f'  Created doc: {d.title} v{d.version}')

content = (project_path / 'docs/test.md').read_text()
base_hash = compute_content_hash((project_path / 'docs/test.md').read_bytes())
modified = content.replace('# Test', '# Updated')
d2 = save_document(project_path, 'docs/test.md', modified, base_hash, 'web')
print(f'  Saved v{d2.version}')

r = asyncio.run(reconcile_project(project_path))
print(f'  Reconciled: {r.files_scanned} scanned, {r.versions_created} created')

report = check_project(project_path)
print(f'  Doctor: healthy={report.is_healthy}, errors={len(report.errors)}')
assert report.is_healthy, f'Doctor found errors: {report.errors}'

import shutil
shutil.rmtree(project_path)
print('  Cleaned up. PASS')
"
cd "$REPO_DIR"
echo ""

# --- 6. REST API integration (hit actual HTTP endpoints) ---
echo "--- 6. REST API integration ---"
API="http://localhost:8001/api/v1"

# Clean up test data from previous runs (DB persists on ZFS)
cleanup_api_test_state "$API_TEST_SLUG"

# Create project via API
echo "  Creating project via API..."
PROJECT=$(curl --fail-with-body -sS -X POST "$API/projects" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"API Test Project\",\"slug\":\"${API_TEST_SLUG}\"}")
echo "    Response: $(echo $PROJECT | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["slug"])')"

# List projects
echo "  Listing projects..."
PROJECTS=$(curl -sf "$API/projects")
COUNT=$(echo $PROJECTS | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
echo "    Count: $COUNT"

# Create document via API
echo "  Creating document via API..."
DOC=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/docs" \
  -H "Content-Type: application/json" \
  -d '{"relative_path":"docs/api-test.md","title":"API Test Doc","doc_type":"plan","content":"# API Test"}')
VERSION=$(echo $DOC | python3 -c 'import sys,json;print(json.load(sys.stdin)["version"])')
echo "    Version: $VERSION"

# Get document
echo "  Getting document via API..."
CONTENT=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/docs/docs/api-test.md")
TITLE=$(echo $CONTENT | python3 -c 'import sys,json;print(json.load(sys.stdin)["metadata"]["title"])')
HASH=$(echo $CONTENT | python3 -c 'import sys,json;print(json.load(sys.stdin)["metadata"]["content_hash"])')
FULL_CONTENT=$(echo $CONTENT | python3 -c 'import sys,json;print(json.load(sys.stdin)["content"])')
echo "    Title: $TITLE"

# Save document (full content round-trip)
echo "  Saving document via API..."
MODIFIED=$(echo "$FULL_CONTENT" | sed 's/# API Test/# Updated via API/')
SAVED=$(curl --fail-with-body -sS -X PUT "$API/projects/${API_TEST_SLUG}/docs/docs/api-test.md" \
  -H "Content-Type: application/json" \
  -d "{\"content\":$(echo "$MODIFIED" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))'),\"base_hash\":\"$HASH\"}")
NEW_VERSION=$(echo $SAVED | python3 -c 'import sys,json;print(json.load(sys.stdin)["version"])')
echo "    New version: $NEW_VERSION"
[ "$NEW_VERSION" = "2" ] || { echo "    FAIL: expected version 2, got $NEW_VERSION"; exit 1; }

# Conflict test
echo "  Testing conflict detection..."
CONFLICT=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$API/projects/${API_TEST_SLUG}/docs/docs/api-test.md" \
  -H "Content-Type: application/json" \
  -d '{"content":"# Should conflict","base_hash":"sha256:wrong"}')
echo "    Conflict status: $CONFLICT (expected 409)"
[ "$CONFLICT" = "409" ] || { echo "    FAIL: expected 409"; exit 1; }

echo "  API tests PASS"
echo ""

# --- 7. Watcher health check ---
echo "--- 7. Watcher health ---"
WATCHER_RUNNING=$(docker compose ps --status running datum-watcher --format '{{.Name}}' 2>/dev/null)
if [ -n "$WATCHER_RUNNING" ]; then
    echo "  datum-watcher container: running"
else
    echo "  FAIL: datum-watcher container not running"
    exit 1
fi
echo ""

# --- 8. Caddy reverse proxy ---
echo "--- 8. Caddy reverse proxy ---"
echo "  Caddy -> API:"
curl -sf http://localhost:3080/api/v1/health | grep -q ok && echo "    OK" || { echo "    FAIL: Caddy not proxying to API"; exit 1; }
echo "  Caddy -> Frontend:"
curl -sf http://localhost:3080/ | grep -q Datum && echo "    OK" || { echo "    FAIL: Caddy not proxying to frontend"; exit 1; }
echo ""

# --- 9. Cleanup ---
echo "--- 9. Cleanup ---"
cleanup_api_test_state "$API_TEST_SLUG"
echo "  Done"
echo ""

echo "=== All integration tests passed ==="
