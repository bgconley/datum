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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
ENV_FILE="$REPO_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

# --- Configuration ---
VENV_PATH="/tank/venvs/datum"
export DATUM_UID="${DATUM_UID:-$(id -u)}"
export DATUM_GID="${DATUM_GID:-$(id -g)}"
export DATUM_PROJECTS_ROOT="${DATUM_PROJECTS_ROOT:-/tank/datum/projects}"
export DATUM_BLOBS_ROOT="${DATUM_BLOBS_ROOT:-/tank/datum/blobs}"
export DATUM_CACHE_ROOT="${DATUM_CACHE_ROOT:-/tank/datum/cache}"
export DATUM_PGDATA="${DATUM_PGDATA:-/tank/datum/pgdata}"
export DATUM_EMBEDDING_ENDPOINT="${DATUM_EMBEDDING_ENDPOINT:-http://localhost:8010}"
export DATUM_RERANKER_ENDPOINT="${DATUM_RERANKER_ENDPOINT:-http://localhost:8011}"
API_TEST_SLUG="api-test"

cleanup_api_test_state() {
    local slug="${1:-$API_TEST_SLUG}"
    local quiet="${2:-0}"

    if [ "$quiet" != "1" ]; then
        echo "  Cleaning previous test data..."
    fi

    (
        cd "$REPO_DIR"
        docker compose exec -T datum-api sh -lc "rm -rf '/tank/datum/projects/${slug}'" >/dev/null 2>&1 || true
        docker compose exec -T paradedb psql -v ON_ERROR_STOP=1 -q -U datum -d datum >/dev/null <<SQL
DELETE FROM search_run_results
WHERE chunk_id IN (
    SELECT dc.id
    FROM document_chunks dc
    JOIN document_versions dv ON dc.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}'
);
DELETE FROM search_runs
WHERE project_scope = '${slug}';
DELETE FROM chunk_embeddings
WHERE chunk_id IN (
    SELECT dc.id
    FROM document_chunks dc
    JOIN document_versions dv ON dc.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}'
);
DELETE FROM technical_terms
WHERE chunk_id IN (
    SELECT dc.id
    FROM document_chunks dc
    JOIN document_versions dv ON dc.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}'
)
   OR version_id IN (
    SELECT dv.id
    FROM document_versions dv
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}'
);
DELETE FROM document_chunks
WHERE version_id IN (
    SELECT dv.id
    FROM document_versions dv
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}'
);
DELETE FROM version_texts
WHERE version_id IN (
    SELECT dv.id
    FROM document_versions dv
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}'
);
DELETE FROM ingestion_jobs
WHERE project_id IN (SELECT id FROM projects WHERE slug = '${slug}')
   OR version_id IN (
       SELECT dv.id
       FROM document_versions dv
       JOIN documents d ON dv.document_id = d.id
       JOIN projects p ON d.project_id = p.id
       WHERE p.slug = '${slug}'
   );
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

cleanup_pytest_db_state() {
    local quiet="${1:-0}"

    if [ "$quiet" != "1" ]; then
        echo "  Cleaning pytest temp DB state..."
    fi

    (
        cd "$REPO_DIR"
        docker compose exec -T paradedb psql -v ON_ERROR_STOP=1 -q -U datum -d datum >/dev/null <<SQL
DELETE FROM search_run_results
WHERE chunk_id IN (
    SELECT dc.id
    FROM document_chunks dc
    JOIN document_versions dv ON dc.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.filesystem_path LIKE '/tmp/pytest-of-%'
);
DELETE FROM chunk_embeddings
WHERE chunk_id IN (
    SELECT dc.id
    FROM document_chunks dc
    JOIN document_versions dv ON dc.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.filesystem_path LIKE '/tmp/pytest-of-%'
);
DELETE FROM technical_terms
WHERE chunk_id IN (
    SELECT dc.id
    FROM document_chunks dc
    JOIN document_versions dv ON dc.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.filesystem_path LIKE '/tmp/pytest-of-%'
)
   OR version_id IN (
    SELECT dv.id
    FROM document_versions dv
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.filesystem_path LIKE '/tmp/pytest-of-%'
);
DELETE FROM document_chunks
WHERE version_id IN (
    SELECT dv.id
    FROM document_versions dv
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.filesystem_path LIKE '/tmp/pytest-of-%'
);
DELETE FROM version_texts
WHERE version_id IN (
    SELECT dv.id
    FROM document_versions dv
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.filesystem_path LIKE '/tmp/pytest-of-%'
);
DELETE FROM ingestion_jobs
WHERE project_id IN (SELECT id FROM projects WHERE filesystem_path LIKE '/tmp/pytest-of-%')
   OR version_id IN (
       SELECT dv.id
       FROM document_versions dv
       JOIN documents d ON dv.document_id = d.id
       JOIN projects p ON d.project_id = p.id
       WHERE p.filesystem_path LIKE '/tmp/pytest-of-%'
   );
DELETE FROM version_head_events
WHERE project_id IN (SELECT id FROM projects WHERE filesystem_path LIKE '/tmp/pytest-of-%')
   OR document_id IN (
       SELECT id FROM documents
       WHERE project_id IN (SELECT id FROM projects WHERE filesystem_path LIKE '/tmp/pytest-of-%')
   );
DELETE FROM audit_events
WHERE project_id IN (SELECT id FROM projects WHERE filesystem_path LIKE '/tmp/pytest-of-%');
DELETE FROM document_versions
WHERE document_id IN (
    SELECT id FROM documents
    WHERE project_id IN (SELECT id FROM projects WHERE filesystem_path LIKE '/tmp/pytest-of-%')
);
DELETE FROM source_files
WHERE project_id IN (SELECT id FROM projects WHERE filesystem_path LIKE '/tmp/pytest-of-%');
DELETE FROM documents
WHERE project_id IN (SELECT id FROM projects WHERE filesystem_path LIKE '/tmp/pytest-of-%');
DELETE FROM projects
WHERE filesystem_path LIKE '/tmp/pytest-of-%';
SQL
    )

    if [ "$quiet" != "1" ]; then
        echo "    OK"
    fi
}

embedding_endpoint_healthy() {
    curl -sf --max-time 2 "${DATUM_EMBEDDING_ENDPOINT}/health" >/dev/null 2>&1
}

reranker_endpoint_healthy() {
    curl -sf --max-time 2 "${DATUM_RERANKER_ENDPOINT}/health" >/dev/null 2>&1
}

wait_for_search_pipeline() {
    local slug="${1:-$API_TEST_SLUG}"
    local timeout_seconds="${2:-45}"
    local require_embeddings="${3:-0}"
    local deadline=$((SECONDS + timeout_seconds))

    echo "  Waiting for ingestion pipeline..."

    while [ "$SECONDS" -lt "$deadline" ]; do
        local counts
        counts="$(
            cd "$REPO_DIR" && docker compose exec -T paradedb psql -tA -F '|' -U datum -d datum <<SQL
SELECT
  COALESCE((
    SELECT count(*)
    FROM version_texts vt
    JOIN document_versions dv ON vt.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}' AND dv.id = d.current_version_id
  ), 0),
  COALESCE((
    SELECT count(*)
    FROM document_chunks dc
    JOIN document_versions dv ON dc.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}' AND dv.id = d.current_version_id
  ), 0),
  COALESCE((
    SELECT count(*)
    FROM technical_terms tt
    JOIN document_versions dv ON tt.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}' AND dv.id = d.current_version_id
  ), 0),
  COALESCE((
    SELECT count(*)
    FROM chunk_embeddings ce
    JOIN document_chunks dc ON ce.chunk_id = dc.id
    JOIN document_versions dv ON dc.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}' AND dv.id = d.current_version_id
  ), 0),
  COALESCE((
    SELECT count(*)
    FROM ingestion_jobs ij
    JOIN document_versions dv ON ij.version_id = dv.id
    JOIN documents d ON dv.document_id = d.id
    JOIN projects p ON d.project_id = p.id
    WHERE p.slug = '${slug}' AND ij.status IN ('queued', 'running')
  ), 0);
SQL
        )"

        local version_texts chunks technical_terms embeddings jobs
        IFS='|' read -r version_texts chunks technical_terms embeddings jobs <<<"$counts"
        version_texts="${version_texts:-0}"
        chunks="${chunks:-0}"
        technical_terms="${technical_terms:-0}"
        embeddings="${embeddings:-0}"
        jobs="${jobs:-0}"

        if [ "$version_texts" -ge 1 ] && [ "$chunks" -ge 1 ] && [ "$technical_terms" -ge 1 ] && [ "$jobs" -eq 0 ]; then
            if [ "$require_embeddings" != "1" ] || [ "$embeddings" -ge 1 ]; then
                echo "    version_texts=$version_texts chunks=$chunks technical_terms=$technical_terms chunk_embeddings=$embeddings jobs=$jobs"
                return 0
            fi
        fi

        sleep 2
    done

    echo "    FAIL: ingestion pipeline did not settle in ${timeout_seconds}s"
    echo "    Worker logs (last 50 lines):"
    (
        cd "$REPO_DIR"
        docker compose logs datum-worker --tail=50 2>/dev/null || true
    )
    return 1
}

trap 'cleanup_api_test_state "$API_TEST_SLUG" 1 || true' EXIT

echo "=== Datum Full-Stack Integration Tests ==="
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "Venv: $VENV_PATH"
echo "UID:GID: ${DATUM_UID}:${DATUM_GID}"
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
echo "  datum-worker:"
docker compose ps --status running datum-worker --format '{{.Name}}' | grep -q datum-worker && echo "    OK" || { echo "    FAIL"; exit 1; }
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
cleanup_pytest_db_state
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
DOC_PAYLOAD="$(python3 - <<'PY'
import json

print(json.dumps({
    "relative_path": "docs/api-test.md",
    "title": "API Test Doc",
    "doc_type": "plan",
    "content": "# API Test\n\nThe API listens on port 8001.\nSet DATABASE_URL before calling GET /api/v1/health.\n",
}))
PY
)"
DOC=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/docs" \
  -H "Content-Type: application/json" \
  -d "$DOC_PAYLOAD")
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

echo "  Checking version history endpoints..."
VERSIONS=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/docs/docs/api-test.md/versions")
VERSION_COUNT=$(echo "$VERSIONS" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
LATEST_VERSION=$(echo "$VERSIONS" | python3 -c 'import sys,json;data=json.load(sys.stdin);print(data[-1]["version_number"] if data else 0)')
[ "$VERSION_COUNT" -ge 2 ] 2>/dev/null || { echo "    FAIL: expected at least 2 versions"; exit 1; }
[ "$LATEST_VERSION" = "2" ] || { echo "    FAIL: expected latest version 2"; exit 1; }

VERSION_ONE=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/docs/docs/api-test.md/versions/1")
echo "$VERSION_ONE" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert "# API Test" in data["content"]'

VERSION_DIFF=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/docs/docs/api-test.md/versions/diff/1/2")
DIFF_ADDITIONS=$(echo "$VERSION_DIFF" | python3 -c 'import sys,json;print(json.load(sys.stdin)["additions"])')
[ "$DIFF_ADDITIONS" -gt 0 ] 2>/dev/null || { echo "    FAIL: version diff reported no additions"; exit 1; }
echo "    Versions: $VERSION_COUNT, latest: v$LATEST_VERSION"

echo "  API tests PASS"
echo ""

# --- 6.5. Search pipeline integration ---
echo "--- 6.5. Search pipeline integration ---"
if embedding_endpoint_healthy; then
    echo "  Embedding endpoint: OK (${DATUM_EMBEDDING_ENDPOINT})"
    REQUIRE_EMBEDDINGS=1
else
    echo "  Embedding endpoint: unavailable (${DATUM_EMBEDDING_ENDPOINT})"
    REQUIRE_EMBEDDINGS=0
fi

wait_for_search_pipeline "$API_TEST_SLUG" 45 "$REQUIRE_EMBEDDINGS"

echo "  Streaming phased search results..."
SEARCH_STREAM=$(curl --fail-with-body -sS -N -X POST "$API/search/stream" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"Updated via API\",\"project\":\"${API_TEST_SLUG}\"}")
STREAM_PHASES=$(echo "$SEARCH_STREAM" | python3 -c 'import sys,json; lines=[json.loads(line) for line in sys.stdin if line.strip()]; print(",".join(item.get("phase","") for item in lines if item.get("event")=="phase"))')
STREAM_FINAL_COUNT=$(echo "$SEARCH_STREAM" | python3 -c 'import sys,json; lines=[json.loads(line) for line in sys.stdin if line.strip()]; phases=[item for item in lines if item.get("event")=="phase"]; print(phases[-1]["result_count"] if phases else 0)')
STREAM_RERANK_APPLIED=$(echo "$SEARCH_STREAM" | python3 -c 'import sys,json; lines=[json.loads(line) for line in sys.stdin if line.strip()]; phases=[item for item in lines if item.get("event")=="phase"]; print(phases[-1].get("rerank_applied", False) if phases else False)')
echo "    Stream phases: ${STREAM_PHASES:-none}"
[ "$STREAM_PHASES" = "lexical,reranked" ] || { echo "    FAIL: expected lexical,reranked phases"; exit 1; }
[ "$STREAM_FINAL_COUNT" -ge 1 ] 2>/dev/null || { echo "    FAIL: stream final phase returned 0 results"; exit 1; }
if reranker_endpoint_healthy; then
    [ "$STREAM_RERANK_APPLIED" = "True" ] || { echo "    FAIL: expected rerank_applied true"; exit 1; }
fi

echo "  Searching current-version content..."
SEARCH_UPDATED=$(curl --fail-with-body -sS -X POST "$API/search" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"Updated via API\",\"project\":\"${API_TEST_SLUG}\"}")
UPDATED_COUNT=$(echo "$SEARCH_UPDATED" | python3 -c 'import sys,json; print(json.load(sys.stdin)["result_count"])')
UPDATED_PATH=$(echo "$SEARCH_UPDATED" | python3 -c 'import sys,json; data=json.load(sys.stdin); print(data["results"][0]["document_path"] if data["results"] else "")')
echo "    Query 'Updated via API' results: $UPDATED_COUNT"
[ "$UPDATED_COUNT" -ge 1 ] 2>/dev/null || { echo "    FAIL: current-version BM25 search returned 0 results"; exit 1; }
[ "$UPDATED_PATH" = "docs/api-test.md" ] || { echo "    FAIL: unexpected top result path: $UPDATED_PATH"; exit 1; }

echo "  Searching technical term..."
SEARCH_TERM=$(curl --fail-with-body -sS -X POST "$API/search" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"DATABASE_URL\",\"project\":\"${API_TEST_SLUG}\"}")
TERM_COUNT=$(echo "$SEARCH_TERM" | python3 -c 'import sys,json; print(json.load(sys.stdin)["result_count"])')
MATCHED_TERMS=$(echo "$SEARCH_TERM" | python3 -c 'import sys,json; data=json.load(sys.stdin); print(",".join(data["results"][0]["matched_terms"]) if data["results"] else "")')
echo "    Query 'DATABASE_URL' results: $TERM_COUNT"
[ "$TERM_COUNT" -ge 1 ] 2>/dev/null || { echo "    FAIL: technical-term search returned 0 results"; exit 1; }
echo "    Matched terms: ${MATCHED_TERMS:-none}"
echo ""

# --- 6.6. Evaluation harness integration ---
echo "--- 6.6. Evaluation harness ---"
echo "  Creating evaluation set..."
EVAL_SET=$(curl --fail-with-body -sS -X POST "$API/eval/sets" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"integration-test-set\",\"queries\":[{\"query\":\"Updated via API\",\"expected_results\":[{\"doc_path\":\"docs/api-test.md\",\"rank_threshold\":1}]}]}")
EVAL_SET_ID=$(echo "$EVAL_SET" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
[ -n "$EVAL_SET_ID" ] || { echo "    FAIL: evaluation set creation returned no ID"; exit 1; }
echo "    Created: $EVAL_SET_ID"

echo "  Running evaluation..."
EVAL_RUN=$(curl --fail-with-body -sS -X POST "$API/eval/runs" \
  -H "Content-Type: application/json" \
  -d "{\"eval_set_id\":\"${EVAL_SET_ID}\",\"name\":\"integration-eval-run\",\"version_scope\":\"current\",\"reranker_enabled\":true}")
EVAL_RUN_ID=$(echo "$EVAL_RUN" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
[ -n "$EVAL_RUN_ID" ] || { echo "    FAIL: evaluation run returned no ID"; exit 1; }
echo "    Eval run: $EVAL_RUN_ID"

echo "  Listing evaluation sets..."
SET_COUNT=$(curl --fail-with-body -sS "$API/eval/sets" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
[ "$SET_COUNT" -gt 0 ] || { echo "    FAIL: no evaluation sets found"; exit 1; }
echo "    Count: $SET_COUNT"

echo "  Checking embedding stats..."
EMBED_MODEL_COUNT=$(curl --fail-with-body -sS "$API/eval/stats" | python3 -c 'import sys,json;print(len(json.load(sys.stdin).get("models", [])))')
echo "    Stats: ${EMBED_MODEL_COUNT} embedding model(s)"

if reranker_endpoint_healthy; then
    echo "  Verifying rerank telemetry..."
    RERANK_ROWS="$(
      cd "$REPO_DIR" && docker compose exec -T paradedb psql -tA -U datum -d datum <<SQL
SELECT count(*)
FROM search_run_results srr
JOIN search_runs sr ON sr.id = srr.search_run_id
WHERE sr.reranker_model_run_id IS NOT NULL
  AND srr.rerank_score IS NOT NULL
  AND sr.project_scope = '${API_TEST_SLUG}';
SQL
    )"
    [ "${RERANK_ROWS:-0}" -gt 0 ] 2>/dev/null || { echo "    FAIL: rerank telemetry missing"; exit 1; }
fi
echo "  Evaluation harness: OK"
echo ""

# --- 7. Background workers health check ---
echo "--- 7. Background workers health ---"
WATCHER_RUNNING=$(docker compose ps --status running datum-watcher --format '{{.Name}}' 2>/dev/null)
if [ -n "$WATCHER_RUNNING" ]; then
    echo "  datum-watcher container: running"
else
    echo "  FAIL: datum-watcher container not running"
    exit 1
fi
WORKER_RUNNING=$(docker compose ps --status running datum-worker --format '{{.Name}}' 2>/dev/null)
if [ -n "$WORKER_RUNNING" ]; then
    echo "  datum-worker container: running"
else
    echo "  FAIL: datum-worker container not running"
    exit 1
fi
echo ""

# --- 8. Caddy reverse proxy ---
echo "--- 8. Caddy reverse proxy ---"
echo "  Caddy -> API:"
curl -sf http://localhost:3080/api/v1/health | grep -q ok && echo "    OK" || { echo "    FAIL: Caddy not proxying to API"; exit 1; }
echo "  Caddy -> Frontend:"
curl -sf http://localhost:3080/ | grep -q Datum && echo "    OK" || { echo "    FAIL: Caddy not proxying to frontend"; exit 1; }
echo "  Caddy -> Routed search page:"
curl -sf http://localhost:3080/search | grep -q Datum && echo "    OK" || { echo "    FAIL: routed /search page not served"; exit 1; }
echo "  Caddy -> Routed document history page:"
curl -sf "http://localhost:3080/projects/${API_TEST_SLUG}/docs/docs/api-test.md/history" | grep -q Datum && echo "    OK" || { echo "    FAIL: routed document history page not served"; exit 1; }
echo ""

# --- 9. Cleanup ---
echo "--- 9. Cleanup ---"
cleanup_api_test_state "$API_TEST_SLUG"
echo "  Done"
echo ""

echo "=== All integration tests passed ==="
