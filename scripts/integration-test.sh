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
#   - GLiNER NER service bootstrapped and running
#     (scripts/bootstrap-gliner-gpu-node.sh + scripts/run-gliner-gpu-node.sh)
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
export DATUM_NER_ENDPOINT="${DATUM_NER_ENDPOINT:-http://localhost:8012}"
export DATUM_LIFECYCLE_ENFORCEMENT_MODE="${DATUM_LIFECYCLE_ENFORCEMENT_MODE:-blocking}"
export INTEGRATION_RUN_ID="${INTEGRATION_RUN_ID:-$(date +%s)-$$}"
export PHASE6_KEY_NAME_PREFIX="${PHASE6_KEY_NAME_PREFIX:-integration-test-phase6}"
export PHASE6_IDEMPOTENCY_PREFIX="${PHASE6_IDEMPOTENCY_PREFIX:-phase6-integration}"
API_TEST_SLUG="api-test"

run_project_graph_cleanup() {
    local project_selector_sql="$1"

    (
        cd "$REPO_DIR"
        docker compose exec -T paradedb psql -v ON_ERROR_STOP=1 -q -U datum -d datum >/dev/null <<SQL
DO \$\$
DECLARE
    fk RECORD;
BEGIN
    CREATE TEMP TABLE _target_projects (id uuid PRIMARY KEY) ON COMMIT DROP;
    INSERT INTO _target_projects
    ${project_selector_sql};

    IF NOT EXISTS (SELECT 1 FROM _target_projects) THEN
        RETURN;
    END IF;

    CREATE TEMP TABLE _target_project_slugs (slug text PRIMARY KEY) ON COMMIT DROP;
    INSERT INTO _target_project_slugs
    SELECT slug FROM projects WHERE id IN (SELECT id FROM _target_projects);

    CREATE TEMP TABLE _target_documents (id uuid PRIMARY KEY) ON COMMIT DROP;
    INSERT INTO _target_documents
    SELECT id FROM documents WHERE project_id IN (SELECT id FROM _target_projects);

    CREATE TEMP TABLE _target_versions (id uuid PRIMARY KEY) ON COMMIT DROP;
    INSERT INTO _target_versions
    SELECT id FROM document_versions WHERE document_id IN (SELECT id FROM _target_documents);

    CREATE TEMP TABLE _target_chunks (id uuid PRIMARY KEY) ON COMMIT DROP;
    INSERT INTO _target_chunks
    SELECT id FROM document_chunks WHERE version_id IN (SELECT id FROM _target_versions);

    -- Delete leaf rows that point at chunks.
    FOR fk IN
        SELECT tc.table_schema, tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND ccu.table_schema = 'public'
          AND ccu.table_name = 'document_chunks'
          AND ccu.column_name = 'id'
    LOOP
        IF fk.table_name <> 'document_chunks' THEN
            EXECUTE format(
                'DELETE FROM %I.%I WHERE %I IN (SELECT id FROM _target_chunks)',
                fk.table_schema, fk.table_name, fk.column_name
            );
        END IF;
    END LOOP;

    -- Delete rows that point at document versions.
    FOR fk IN
        SELECT tc.table_schema, tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND ccu.table_schema = 'public'
          AND ccu.table_name = 'document_versions'
          AND ccu.column_name = 'id'
    LOOP
        IF fk.table_name <> 'document_versions' THEN
            EXECUTE format(
                'DELETE FROM %I.%I WHERE %I IN (SELECT id FROM _target_versions)',
                fk.table_schema, fk.table_name, fk.column_name
            );
        END IF;
    END LOOP;

    -- Delete rows that point at documents.
    FOR fk IN
        SELECT tc.table_schema, tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND ccu.table_schema = 'public'
          AND ccu.table_name = 'documents'
          AND ccu.column_name = 'id'
    LOOP
        IF fk.table_name <> 'documents' THEN
            EXECUTE format(
                'DELETE FROM %I.%I WHERE %I IN (SELECT id FROM _target_documents)',
                fk.table_schema, fk.table_name, fk.column_name
            );
        END IF;
    END LOOP;

    -- Delete rows that point at projects.
    FOR fk IN
        SELECT tc.table_schema, tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND ccu.table_schema = 'public'
          AND ccu.table_name = 'projects'
          AND ccu.column_name = 'id'
    LOOP
        IF fk.table_name <> 'projects' THEN
            EXECUTE format(
                'DELETE FROM %I.%I WHERE %I IN (SELECT id FROM _target_projects)',
                fk.table_schema, fk.table_name, fk.column_name
            );
        END IF;
    END LOOP;

    -- Non-FK selectors that still need deterministic cleanup.
    IF to_regclass('public.search_runs') IS NOT NULL THEN
        DELETE FROM search_runs
        WHERE project_scope IN (SELECT slug FROM _target_project_slugs);
    END IF;

    -- Remove core graph roots.
    DELETE FROM document_chunks WHERE id IN (SELECT id FROM _target_chunks);
    DELETE FROM document_versions WHERE id IN (SELECT id FROM _target_versions);
    DELETE FROM documents WHERE id IN (SELECT id FROM _target_documents);
    DELETE FROM source_files WHERE project_id IN (SELECT id FROM _target_projects);
    DELETE FROM projects WHERE id IN (SELECT id FROM _target_projects);

    -- Keep entities table compact after mention deletion.
    DELETE FROM entities e
    WHERE NOT EXISTS (
        SELECT 1
        FROM entity_mentions em
        WHERE em.entity_id = e.id
    );
END \$\$;
SQL
    )
}

cleanup_api_test_state() {
    local slug="${1:-$API_TEST_SLUG}"
    local quiet="${2:-0}"

    if [ "$quiet" != "1" ]; then
        echo "  Cleaning previous test data..."
    fi

    rm -rf "${DATUM_PROJECTS_ROOT}/${slug}" 2>/dev/null || true
    (
        cd "$REPO_DIR"
        docker compose exec -T datum-api sh -lc "rm -rf '/tank/datum/projects/${slug}'" >/dev/null 2>&1 || true
    )

    run_project_graph_cleanup "SELECT id FROM projects WHERE slug = '${slug}'"

    (
        cd "$REPO_DIR"
        docker compose exec -T paradedb psql -v ON_ERROR_STOP=1 -q -U datum -d datum >/dev/null <<SQL
DO \$\$
BEGIN
    IF to_regclass('public.idempotency_records') IS NOT NULL THEN
        DELETE FROM idempotency_records
        WHERE idempotency_key LIKE '${PHASE6_IDEMPOTENCY_PREFIX}-%';
    END IF;

    IF to_regclass('public.api_keys') IS NOT NULL THEN
        DELETE FROM api_keys
        WHERE name LIKE '${PHASE6_KEY_NAME_PREFIX}-%';
    END IF;

    IF to_regclass('public.agent_sessions') IS NOT NULL THEN
        DELETE FROM agent_sessions
        WHERE session_id LIKE '%${INTEGRATION_RUN_ID}%'
           OR project_id IS NULL
              AND session_id LIKE 'phase9-%';
    END IF;
END \$\$;
SQL
    )

    if [ "$quiet" != "1" ]; then
        echo "    OK"
    fi
}

cleanup_pytest_db_state() {
    local quiet="${1:-0}"

    if [ "$quiet" != "1" ]; then
        echo "  Cleaning pytest temp DB state..."
    fi

    run_project_graph_cleanup "SELECT id FROM projects WHERE filesystem_path LIKE '/tmp/pytest-of-%'"

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

ner_endpoint_healthy() {
    curl -sf --max-time 2 "${DATUM_NER_ENDPOINT}/health" >/dev/null 2>&1
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
echo "Lifecycle enforcement: ${DATUM_LIFECYCLE_ENFORCEMENT_MODE}"
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
TITLE=$(echo "$CONTENT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["metadata"]["title"])')
HASH=$(echo "$CONTENT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["metadata"]["content_hash"])')
DOC_UID=$(echo "$CONTENT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["metadata"]["document_uid"])')
VERSION_ID=$(echo "$CONTENT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["metadata"].get("version_id") or "")')
FULL_CONTENT=$(echo "$CONTENT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["content"])')
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

# --- 6.6. Intelligence pipeline integration ---
echo "--- 6.6. Intelligence pipeline ---"
if ner_endpoint_healthy; then
    echo "  NER endpoint: OK (${DATUM_NER_ENDPOINT})"
else
    echo "  FAIL: NER endpoint unavailable (${DATUM_NER_ENDPOINT})"
    echo "  Bootstrap: bash scripts/bootstrap-gliner-gpu-node.sh"
    echo "  Run: CUDA_VISIBLE_DEVICES=1 DATUM_GLINER_DEVICE=cuda:0 DATUM_GLINER_HOST=0.0.0.0 bash scripts/run-gliner-gpu-node.sh"
    exit 1
fi

echo "  Creating schema, ADR, and requirement documents..."
SCHEMA_PAYLOAD="$(python3 - <<'PY'
import json

print(json.dumps({
    "relative_path": "docs/schema/users.sql",
    "title": "users.sql",
    "doc_type": "spec",
    "content": (
        "CREATE TABLE users (\n"
        "    id UUID PRIMARY KEY,\n"
        "    email TEXT NOT NULL\n"
        ");\n\n"
        "CREATE TABLE sessions (\n"
        "    id UUID PRIMARY KEY,\n"
        "    user_id UUID REFERENCES users(id)\n"
        ");\n"
    ),
}))
PY
)"
curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/docs" \
  -H "Content-Type: application/json" \
  -d "$SCHEMA_PAYLOAD" >/dev/null

ADR_PAYLOAD="$(python3 - <<'PY'
import json

print(json.dumps({
    "relative_path": "docs/decisions/adr-0001.md",
    "title": "ADR-0001",
    "doc_type": "decision",
    "content": (
        "# ADR-0001: Use ParadeDB\n\n"
        "## Status\n"
        "Accepted\n\n"
        "## Context\n"
        "Need hybrid search and linked operational schema.\n\n"
        "## Decision\n"
        "Use ParadeDB for BM25 plus pgvector and adopt the "
        "[session schema](docs/schema/users.sql).\n\n"
        "## Consequences\n"
        "Single database for search with explicit schema traceability.\n"
    ),
}))
PY
)"
curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/docs" \
  -H "Content-Type: application/json" \
  -d "$ADR_PAYLOAD" >/dev/null

REQ_PAYLOAD="$(python3 - <<'PY'
import json

print(json.dumps({
    "relative_path": "docs/requirements/auth.md",
    "title": "Auth requirements",
    "doc_type": "spec",
    "content": (
        "# Auth requirements\n\n"
        "REQ-001: The system must persist session ownership as defined in the "
        "[ParadeDB decision](docs/decisions/adr-0001.md).\n\n"
        "See also [missing reference](docs/specs/missing.md).\n"
    ),
}))
PY
)"
curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/docs" \
  -H "Content-Type: application/json" \
  -d "$REQ_PAYLOAD" >/dev/null

wait_for_search_pipeline "$API_TEST_SLUG" 45 "$REQUIRE_EMBEDDINGS"

echo "  Checking inbox..."
PHASE5_LIFECYCLE_SESSION_ID="phase5-${INTEGRATION_RUN_ID}"
curl --fail-with-body -sS -X POST "$API/agent/sessions/start" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${PHASE5_LIFECYCLE_SESSION_ID}\",\"project_slug\":\"${API_TEST_SLUG}\",\"client_type\":\"integration\"}" >/dev/null
INBOX=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/inbox" \
  -H "X-Session-ID: ${PHASE5_LIFECYCLE_SESSION_ID}")
INBOX_COUNT=$(echo "$INBOX" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
HAS_DECISION=$(echo "$INBOX" | python3 -c 'import sys,json;items=json.load(sys.stdin);print(any(item["candidate_type"]=="decision" for item in items))')
HAS_REQUIREMENT=$(echo "$INBOX" | python3 -c 'import sys,json;items=json.load(sys.stdin);print(any(item["candidate_type"]=="requirement" for item in items))')
DECISION_CANDIDATE_ID=$(echo "$INBOX" | python3 -c 'import sys,json;items=json.load(sys.stdin);print(next((item["id"] for item in items if item["candidate_type"]=="decision"), ""))')
REQUIREMENT_CANDIDATE_ID=$(echo "$INBOX" | python3 -c 'import sys,json;items=json.load(sys.stdin);print(next((item["id"] for item in items if item["candidate_type"]=="requirement"), ""))')
echo "    Inbox candidates: $INBOX_COUNT"
[ "$INBOX_COUNT" -gt 0 ] 2>/dev/null || { echo "    FAIL: expected inbox candidates"; exit 1; }
[ "$HAS_DECISION" = "True" ] || { echo "    FAIL: expected decision candidate from ADR"; exit 1; }
[ "$HAS_REQUIREMENT" = "True" ] || { echo "    FAIL: expected requirement candidate"; exit 1; }
[ -n "$DECISION_CANDIDATE_ID" ] || { echo "    FAIL: missing decision candidate id"; exit 1; }
[ -n "$REQUIREMENT_CANDIDATE_ID" ] || { echo "    FAIL: missing requirement candidate id"; exit 1; }

echo "  Accepting extracted requirement and decision candidates..."
curl --fail-with-body -sS -X POST \
  "$API/projects/${API_TEST_SLUG}/inbox/decision/${DECISION_CANDIDATE_ID}/accept" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: ${PHASE5_LIFECYCLE_SESSION_ID}" \
  -d '{}' >/dev/null
curl --fail-with-body -sS -X POST \
  "$API/projects/${API_TEST_SLUG}/inbox/requirement/${REQUIREMENT_CANDIDATE_ID}/accept" \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: ${PHASE5_LIFECYCLE_SESSION_ID}" \
  -d '{}' >/dev/null

echo "  Checking detected document links..."
LINKS=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/links")
LINK_COUNT=$(echo "$LINKS" | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])')
[ "$LINK_COUNT" -ge 2 ] 2>/dev/null || { echo "    FAIL: expected at least 2 document links"; exit 1; }
echo "$LINKS" | python3 -c 'import sys,json; data=json.load(sys.stdin)["links"]; pairs={(item["source_document_path"], item["target_document_path"]) for item in data}; assert ("docs/requirements/auth.md", "docs/decisions/adr-0001.md") in pairs; assert ("docs/decisions/adr-0001.md", "docs/schema/users.sql") in pairs'
echo "    Links: $LINK_COUNT"

echo "  Checking extracted entities..."
ENTITY_COUNT="$(
  cd "$REPO_DIR" && docker compose exec -T paradedb psql -tA -U datum -d datum <<SQL
SELECT count(*)
FROM entity_mentions em
JOIN document_versions dv ON em.version_id = dv.id
JOIN documents d ON dv.document_id = d.id
JOIN projects p ON d.project_id = p.id
WHERE p.slug = '${API_TEST_SLUG}';
SQL
)"
echo "    Entity mentions: ${ENTITY_COUNT:-0}"
[ "${ENTITY_COUNT:-0}" -gt 0 ] 2>/dev/null || { echo "    FAIL: expected entity mentions from GLiNER"; exit 1; }

echo "  Checking entity relationships and graph APIs..."
RELATIONSHIPS=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/relationships")
REL_COUNT=$(echo "$RELATIONSHIPS" | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])')
[ "$REL_COUNT" -gt 0 ] 2>/dev/null || { echo "    FAIL: expected schema/entity relationships"; exit 1; }
echo "$RELATIONSHIPS" | python3 -c 'import sys,json; data=json.load(sys.stdin)["relationships"]; assert any(item["relationship_type"] == "foreign_key" for item in data)'
ENTITIES=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/entities")
ENTITY_TOTAL=$(echo "$ENTITIES" | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])')
[ "$ENTITY_TOTAL" -gt 0 ] 2>/dev/null || { echo "    FAIL: expected entity graph results"; exit 1; }
ENTITY_ID=$(echo "$ENTITIES" | python3 -c 'import sys,json; data=json.load(sys.stdin); print(data["entities"][0]["id"] if data["entities"] else "")')
[ -n "$ENTITY_ID" ] || { echo "    FAIL: expected entity id"; exit 1; }
ENTITY_DETAIL=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/entities/${ENTITY_ID}")
echo "$ENTITY_DETAIL" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["mention_count"] >= 1; assert isinstance(data["relationships"], list)'
echo "    Relationships: $REL_COUNT, entities: $ENTITY_TOTAL"

echo "  Running insight analysis via CLI..."
INSIGHTS_ANALYZE_OUTPUT="$(cd "$BACKEND_DIR" && datum insights analyze "$API_TEST_SLUG")"
INSIGHTS_CREATED=$(echo "$INSIGHTS_ANALYZE_OUTPUT" | awk '/Insights created:/ {print $3}')
[ "${INSIGHTS_CREATED:-0}" -gt 0 ] 2>/dev/null || { echo "    FAIL: expected CLI insight analysis to create insights"; echo "$INSIGHTS_ANALYZE_OUTPUT"; exit 1; }
INSIGHTS_LIST_OUTPUT="$(cd "$BACKEND_DIR" && datum insights list "$API_TEST_SLUG")"
echo "$INSIGHTS_LIST_OUTPUT" | grep -q "Broken link:" || { echo "    FAIL: expected broken-link insight in CLI output"; exit 1; }

echo "  Checking insights and traceability endpoints..."
INSIGHTS=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/insights")
INSIGHT_TOTAL=$(echo "$INSIGHTS" | python3 -c 'import sys,json;print(json.load(sys.stdin)["total"])')
[ "$INSIGHT_TOTAL" -gt 0 ] 2>/dev/null || { echo "    FAIL: expected insights from analysis"; exit 1; }
INSIGHT_ID=$(echo "$INSIGHTS" | python3 -c 'import sys,json; data=json.load(sys.stdin); print(data["insights"][0]["id"] if data["insights"] else "")')
[ -n "$INSIGHT_ID" ] || { echo "    FAIL: missing insight id"; exit 1; }
UPDATED_INSIGHT=$(curl --fail-with-body -sS -X POST \
  "$API/projects/${API_TEST_SLUG}/insights/${INSIGHT_ID}/status" \
  -H "Content-Type: application/json" \
  -d '{"status":"acknowledged"}')
echo "$UPDATED_INSIGHT" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["status"] == "acknowledged"'

TRACEABILITY=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/traceability")
TRACE_COUNT=$(echo "$TRACEABILITY" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
[ "$TRACE_COUNT" -gt 0 ] 2>/dev/null || { echo "    FAIL: expected traceability chains"; exit 1; }
echo "$TRACEABILITY" | python3 -c 'import sys,json; chains=json.load(sys.stdin); assert chains[0]["decisions"]; assert chains[0]["schema_entities"]'
echo "    Insights: $INSIGHT_TOTAL, traceability chains: $TRACE_COUNT"
echo ""

# --- 6.7. Evaluation harness integration ---
echo "--- 6.7. Evaluation harness ---"
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

# --- 6.8. Phase 8 operational surfaces ---
echo "--- 6.8. Phase 8 operational surfaces ---"
echo "  Checking templates..."
TEMPLATES=$(curl --fail-with-body -sS "$API/templates")
TEMPLATE_COUNT=$(echo "$TEMPLATES" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
[ "$TEMPLATE_COUNT" -ge 4 ] 2>/dev/null || { echo "    FAIL: expected at least 4 templates"; exit 1; }
ADR_TEMPLATE=$(curl --fail-with-body -sS "$API/templates/adr/render?title=ADR-9000")
echo "$ADR_TEMPLATE" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["doc_type"] == "decision"; assert "ADR-9000" in data["content"]'
echo "    Templates: $TEMPLATE_COUNT available"

echo "  Checking saved searches..."
SAVED_SEARCH=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/saved-searches" \
  -H "Content-Type: application/json" \
  -d '{"name":"Updated API docs","query_text":"Updated via API","filters":{"scope":"current"}}')
SAVED_SEARCH_ID=$(echo "$SAVED_SEARCH" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
[ -n "$SAVED_SEARCH_ID" ] || { echo "    FAIL: saved search creation returned no id"; exit 1; }
SAVED_SEARCHES=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/saved-searches")
SAVED_SEARCH_COUNT=$(echo "$SAVED_SEARCHES" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
[ "$SAVED_SEARCH_COUNT" -ge 1 ] 2>/dev/null || { echo "    FAIL: expected saved search listing"; exit 1; }
echo "    Saved searches: $SAVED_SEARCH_COUNT"

echo "  Checking collections..."
COLLECTION=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/collections" \
  -H "Content-Type: application/json" \
  -d '{"name":"API docs","description":"Integration-managed collection"}')
COLLECTION_ID=$(echo "$COLLECTION" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
[ -n "$COLLECTION_ID" ] || { echo "    FAIL: collection creation returned no id"; exit 1; }
curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/collections/${COLLECTION_ID}/members" \
  -H "Content-Type: application/json" \
  -d "{\"document_uid\":\"${DOC_UID}\"}" >/dev/null
COLLECTION_MEMBERS=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/collections/${COLLECTION_ID}/members")
echo "$COLLECTION_MEMBERS" | python3 -c 'import sys,json; members=json.load(sys.stdin); assert any(item["document_uid"] == sys.argv[1] for item in members)' "$DOC_UID"
echo "    Collection: OK"

echo "  Checking annotations..."
[ -n "$VERSION_ID" ] || { echo "    FAIL: missing version_id for annotation test"; exit 1; }
ANNOTATION=$(curl --fail-with-body -sS -X POST "$API/annotations" \
  -H "Content-Type: application/json" \
  -d "{\"version_id\":\"${VERSION_ID}\",\"annotation_type\":\"comment\",\"content\":\"Integration note\",\"start_char\":0,\"end_char\":12}")
ANNOTATION_ID=$(echo "$ANNOTATION" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
[ -n "$ANNOTATION_ID" ] || { echo "    FAIL: annotation creation returned no id"; exit 1; }
ANNOTATIONS=$(curl --fail-with-body -sS "$API/annotations?version_id=${VERSION_ID}")
ANNOTATION_COUNT=$(echo "$ANNOTATIONS" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
[ "$ANNOTATION_COUNT" -ge 1 ] 2>/dev/null || { echo "    FAIL: expected annotation listing"; exit 1; }
echo "    Annotations: $ANNOTATION_COUNT"

echo "  Checking upload and mkdir..."
PHASE8_UPLOAD_FILE="/tmp/datum-phase8-upload-${INTEGRATION_RUN_ID}.txt"
echo "phase 8 upload" > "$PHASE8_UPLOAD_FILE"
UPLOAD=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/upload" \
  -F "file=@${PHASE8_UPLOAD_FILE}")
rm -f "$PHASE8_UPLOAD_FILE"
UPLOAD_HASH=$(echo "$UPLOAD" | python3 -c 'import sys,json;print(json.load(sys.stdin)["content_hash"])')
UPLOAD_ATTACHMENT=$(echo "$UPLOAD" | python3 -c 'import sys,json;print(json.load(sys.stdin)["attachment_path"])')
[[ "$UPLOAD_HASH" == sha256:* ]] || { echo "    FAIL: upload hash missing"; exit 1; }
[ -n "$UPLOAD_ATTACHMENT" ] || { echo "    FAIL: upload attachment path missing"; exit 1; }
curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/fs/mkdir" \
  -H "Content-Type: application/json" \
  -d '{"path":"docs/ops"}' >/dev/null
[ -d "${DATUM_PROJECTS_ROOT}/${API_TEST_SLUG}/docs/ops" ] || { echo "    FAIL: mkdir did not create docs/ops"; exit 1; }
echo "    Upload + mkdir: OK"

echo "  Checking operational scripts..."
for script in backup.sh restore-drill.sh snapshot-policy.sh benchmark-queries.py; do
    [ -x "$REPO_DIR/scripts/$script" ] || { echo "    FAIL: scripts/$script missing or not executable"; exit 1; }
done
for unit in datum-embedder.service datum-reranker.service gliner-ner.service; do
    [ -f "$REPO_DIR/systemd/$unit" ] || { echo "    FAIL: systemd/$unit missing"; exit 1; }
done
echo "    Scripts + systemd files: OK"
echo ""

# --- 6.9. Agent API & MCP ---
echo "--- 6.9. Agent API & MCP ---"
PHASE6_ADMIN_NAME="${PHASE6_KEY_NAME_PREFIX}-admin-${INTEGRATION_RUN_ID}"
PHASE6_RW_NAME="${PHASE6_KEY_NAME_PREFIX}-rw-${INTEGRATION_RUN_ID}"
PHASE6_RO_NAME="${PHASE6_KEY_NAME_PREFIX}-ro-${INTEGRATION_RUN_ID}"
PHASE6_SESSION_ID="sess-${INTEGRATION_RUN_ID}"
PHASE6_IDEM_SESSION_ID="idem-sess-${INTEGRATION_RUN_ID}"
PHASE6_CREATE_IDEM_KEY="${PHASE6_IDEMPOTENCY_PREFIX}-create-${INTEGRATION_RUN_ID}"
PHASE6_IDEM_IDEM_KEY="${PHASE6_IDEMPOTENCY_PREFIX}-idem-${INTEGRATION_RUN_ID}"

echo "  Bootstrapping admin API key..."
ADMIN_KEY_OUTPUT="$(python "$REPO_DIR/scripts/create-admin-key.py" \
  --name "$PHASE6_ADMIN_NAME" \
  --created-by "integration-test")"
PHASE6_ADMIN_KEY="$(echo "$ADMIN_KEY_OUTPUT" | awk '/^Key:/ {print $2}')"
[ -n "$PHASE6_ADMIN_KEY" ] || { echo "    FAIL: could not create admin key"; exit 1; }
echo "    Admin key: OK"

echo "  Creating scoped API keys..."
RW_KEY_RESP=$(curl --fail-with-body -sS -X POST "$API/admin/api-keys" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_ADMIN_KEY" \
  -d "{\"name\":\"${PHASE6_RW_NAME}\",\"scope\":\"readwrite\"}")
PHASE6_RW_KEY="$(echo "$RW_KEY_RESP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["key"])')"
[ -n "$PHASE6_RW_KEY" ] || { echo "    FAIL: readwrite key missing"; exit 1; }

RO_KEY_RESP=$(curl --fail-with-body -sS -X POST "$API/admin/api-keys" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_ADMIN_KEY" \
  -d "{\"name\":\"${PHASE6_RO_NAME}\",\"scope\":\"read\"}")
PHASE6_RO_KEY="$(echo "$RO_KEY_RESP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["key"])')"
[ -n "$PHASE6_RO_KEY" ] || { echo "    FAIL: read-only key missing"; exit 1; }
echo "    Keys: admin + readwrite + read"

echo "  Verifying scope enforcement on admin endpoints..."
SCOPE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/admin/api-keys" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_RO_KEY" \
  -d "{\"name\":\"${PHASE6_KEY_NAME_PREFIX}-should-fail-${INTEGRATION_RUN_ID}\",\"scope\":\"read\"}")
[ "$SCOPE_STATUS" = "403" ] || { echo "    FAIL: expected 403 from read-only key, got $SCOPE_STATUS"; exit 1; }
echo "    Read-only key correctly rejected"

echo "  Listing admin-managed API keys..."
KEY_LIST=$(curl --fail-with-body -sS "$API/admin/api-keys" \
  -H "X-API-Key: $PHASE6_ADMIN_KEY")
echo "$KEY_LIST" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert any(item["name"].startswith("integration-test-phase6-") for item in data["keys"])'
echo "    Admin list: OK"

echo "  Creating and appending a session note..."
curl --fail-with-body -sS -X POST "$API/agent/sessions/start" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${PHASE6_SESSION_ID}\",\"project_slug\":\"${API_TEST_SLUG}\",\"client_type\":\"integration\"}" >/dev/null
curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/context?detail=brief&max_tokens=300" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Session-ID: ${PHASE6_SESSION_ID}" >/dev/null
SESSION_CREATE=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/sessions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Idempotency-Key: $PHASE6_CREATE_IDEM_KEY" \
  -H "X-Session-ID: ${PHASE6_SESSION_ID}" \
  -d "{\"session_id\":\"${PHASE6_SESSION_ID}\",\"agent_name\":\"codex\",\"summary\":\"Integration session ${INTEGRATION_RUN_ID}\",\"content\":\"## Session\\nCreated during Phase 6 integration verification.\",\"repo_path\":\"/tank/repos/datum\",\"git_branch\":\"main\",\"files_touched\":[\"docs/api-test.md\"],\"commands_run\":[\"pytest -q\"],\"next_steps\":[\"verify mcp\"]}")
SESSION_PATH="$(echo "$SESSION_CREATE" | python3 -c 'import sys,json;print(json.load(sys.stdin)["path"])')"
[ -n "$SESSION_PATH" ] || { echo "    FAIL: session creation returned no path"; exit 1; }

SESSION_APPEND=$(curl --fail-with-body -sS -X PUT "$API/projects/${API_TEST_SLUG}/sessions/${PHASE6_SESSION_ID}" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Idempotency-Key: ${PHASE6_IDEMPOTENCY_PREFIX}-append-${INTEGRATION_RUN_ID}" \
  -H "X-Session-ID: ${PHASE6_SESSION_ID}" \
  -d "{\"content\":\"## Follow-up\\nAppended content for audit verification.\",\"files_touched\":[\"docs/sessions/${PHASE6_SESSION_ID}.md\"],\"commands_run\":[\"curl /api/v1/projects/${API_TEST_SLUG}/sessions\"],\"next_steps\":[\"review audit\"],\"summary\":\"Integration session ${INTEGRATION_RUN_ID} updated\"}")
echo "$SESSION_APPEND" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["status"] == "appended"'

SESSION_LIST=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/sessions" \
  -H "X-API-Key: $PHASE6_RW_KEY")
SESSION_MATCH_COUNT="$(echo "$SESSION_LIST" | python3 -c 'import sys,json; data=json.load(sys.stdin); print(sum(1 for item in data["sessions"] if item["session_id"] == sys.argv[1]))' "$PHASE6_SESSION_ID")"
[ "$SESSION_MATCH_COUNT" = "1" ] || { echo "    FAIL: expected 1 matching session, got $SESSION_MATCH_COUNT"; exit 1; }
echo "    Session note API: OK"

echo "  Verifying project context budget endpoint..."
CONTEXT_RESP=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/context?detail=brief&max_tokens=400" \
  -H "X-API-Key: $PHASE6_RW_KEY")
echo "$CONTEXT_RESP" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["content_kind"] == "retrieved_project_document"; assert data["data"]["project"]["slug"] == "api-test"; assert isinstance(data["data"]["documents"], list)'
echo "    Context endpoint: OK"

echo "  Resolving an exact citation..."
CITATION_RESP=$(curl --fail-with-body -sS -X POST "$API/citations/resolve" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -d "{\"source_ref\":{\"project_slug\":\"${API_TEST_SLUG}\",\"document_uid\":\"doc_phase6\",\"version_number\":2,\"content_hash\":\"sha256:phase6\",\"chunk_id\":\"chunk_phase6\",\"canonical_path\":\"docs/api-test.md\",\"heading_path\":[],\"line_start\":1,\"line_end\":20}}")
echo "$CITATION_RESP" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert "Updated via API" in (data.get("content") or "")'
echo "    Citation endpoint: OK"

echo "  Querying audit events..."
AUDIT_RESP=$(curl --fail-with-body -sS "$API/admin/audit?actor_type=agent&limit=20" \
  -H "X-API-Key: $PHASE6_ADMIN_KEY")
echo "$AUDIT_RESP" | python3 -c 'import sys,json; data=json.load(sys.stdin); ops={item["operation"] for item in data["events"]}; assert "create_session_note" in ops; assert "append_session_note" in ops'
echo "    Audit query: OK"

echo "  Checking MCP SSE endpoint..."
MCP_EVENT="$(curl -sS -N --max-time 5 "http://localhost:8001/mcp/sse" 2>/dev/null | head -n 2 || true)"
echo "$MCP_EVENT" | grep -q "event: endpoint" || { echo "    FAIL: datum-api MCP SSE did not emit endpoint event"; exit 1; }
echo "$MCP_EVENT" | grep -q "data: /mcp/" || { echo "    FAIL: datum-api MCP SSE did not emit endpoint data"; exit 1; }
MCP_CADDY_EVENT="$(curl -sS -N --max-time 5 "http://localhost:3080/mcp/sse" 2>/dev/null | head -n 2 || true)"
echo "$MCP_CADDY_EVENT" | grep -q "event: endpoint" || { echo "    FAIL: Caddy MCP SSE did not emit endpoint event"; exit 1; }
echo "$MCP_CADDY_EVENT" | grep -q "data: /mcp/" || { echo "    FAIL: Caddy MCP SSE did not emit endpoint data"; exit 1; }
echo "    MCP SSE: datum-api + Caddy emitted endpoint event"

echo "  Verifying idempotent session creation..."
curl --fail-with-body -sS -X POST "$API/agent/sessions/start" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${PHASE6_IDEM_SESSION_ID}\",\"project_slug\":\"${API_TEST_SLUG}\",\"client_type\":\"integration\"}" >/dev/null
curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/context?detail=brief&max_tokens=300" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Session-ID: ${PHASE6_IDEM_SESSION_ID}" >/dev/null
IDEM_RESP1=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/sessions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Idempotency-Key: $PHASE6_IDEM_IDEM_KEY" \
  -H "X-Session-ID: ${PHASE6_IDEM_SESSION_ID}" \
  -d "{\"session_id\":\"${PHASE6_IDEM_SESSION_ID}\",\"agent_name\":\"codex\",\"summary\":\"Idempotency ${INTEGRATION_RUN_ID}\",\"content\":\"## Idempotent\\nFirst create.\"}")
IDEM_RESP2=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/sessions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Idempotency-Key: $PHASE6_IDEM_IDEM_KEY" \
  -H "X-Session-ID: ${PHASE6_IDEM_SESSION_ID}" \
  -d "{\"session_id\":\"${PHASE6_IDEM_SESSION_ID}\",\"agent_name\":\"codex\",\"summary\":\"Idempotency ${INTEGRATION_RUN_ID}\",\"content\":\"## Idempotent\\nFirst create.\"}")
[ "$IDEM_RESP1" = "$IDEM_RESP2" ] || { echo "    FAIL: idempotent create responses differ"; exit 1; }
IDEM_COUNT=$(curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/sessions" \
  -H "X-API-Key: $PHASE6_RW_KEY" | python3 -c 'import sys,json; data=json.load(sys.stdin); print(sum(1 for item in data["sessions"] if item["session_id"] == sys.argv[1]))' "$PHASE6_IDEM_SESSION_ID")
[ "$IDEM_COUNT" = "1" ] || { echo "    FAIL: expected 1 idempotent session note, got $IDEM_COUNT"; exit 1; }
echo "    Idempotency: OK"
echo ""

# --- 6.10. Phase 9 lifecycle enforcement ---
echo "--- 6.10. Phase 9 lifecycle enforcement ---"
PHASE9_SESSION_ID="phase9-${INTEGRATION_RUN_ID}"
PHASE9_SESSION_PATH="docs/sessions/phase9-${INTEGRATION_RUN_ID}.md"

echo "  Starting lifecycle session..."
curl --fail-with-body -sS -X POST "$API/agent/sessions/start" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${PHASE9_SESSION_ID}\",\"project_slug\":\"${API_TEST_SLUG}\",\"client_type\":\"integration\"}" >/dev/null

echo "  Write without preflight -> 428..."
PHASE9_BLOCKED_STATUS=$(curl -s -o /tmp/datum-phase9-blocked.json -w "%{http_code}" \
  -X POST "$API/projects/${API_TEST_SLUG}/sessions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Session-ID: ${PHASE9_SESSION_ID}" \
  -d "{\"session_id\":\"${PHASE9_SESSION_ID}\",\"agent_name\":\"codex\",\"summary\":\"Phase 9 block\",\"content\":\"Blocked until preflight.\"}")
[ "$PHASE9_BLOCKED_STATUS" = "428" ] || { echo "    FAIL: expected 428, got $PHASE9_BLOCKED_STATUS"; cat /tmp/datum-phase9-blocked.json; exit 1; }
python3 -c 'import json,sys; data=json.load(open("/tmp/datum-phase9-blocked.json")); assert data["detail"]["error"] == "preflight_required"'
echo "    OK"

echo "  Recording real preflight..."
curl --fail-with-body -sS "$API/projects/${API_TEST_SLUG}/context?detail=brief&max_tokens=300" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Session-ID: ${PHASE9_SESSION_ID}" >/dev/null

echo "  Write after preflight -> 201..."
PHASE9_CREATE=$(curl --fail-with-body -sS -X POST "$API/projects/${API_TEST_SLUG}/sessions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PHASE6_RW_KEY" \
  -H "X-Session-ID: ${PHASE9_SESSION_ID}" \
  -d "{\"session_id\":\"${PHASE9_SESSION_ID}\",\"agent_name\":\"codex\",\"summary\":\"Phase 9 lifecycle\",\"content\":\"Write after preflight.\"}")
echo "$PHASE9_CREATE" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["path"].startswith("docs/sessions/")'
echo "    OK"

echo "  Status shows dirty session..."
PHASE9_STATUS=$(curl --fail-with-body -sS "$API/agent/sessions/${PHASE9_SESSION_ID}/status")
echo "$PHASE9_STATUS" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["is_dirty"] is True; assert data["unflushed_delta_count"] >= 1'
echo "    OK"

echo "  Finalize while dirty -> 409..."
PHASE9_FINALIZE_STATUS=$(curl -s -o /tmp/datum-phase9-finalize.json -w "%{http_code}" \
  -X POST "$API/agent/sessions/${PHASE9_SESSION_ID}/finalize")
[ "$PHASE9_FINALIZE_STATUS" = "409" ] || { echo "    FAIL: expected 409, got $PHASE9_FINALIZE_STATUS"; cat /tmp/datum-phase9-finalize.json; exit 1; }
python3 -c 'import json,sys; data=json.load(open("/tmp/datum-phase9-finalize.json")); assert data["detail"]["error"] == "dirty_session"'
echo "    OK"

echo "  Flush then finalize..."
PHASE9_FLUSH=$(curl --fail-with-body -sS -X POST "$API/agent/sessions/${PHASE9_SESSION_ID}/flush")
echo "$PHASE9_FLUSH" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["flushed_count"] >= 1'
PHASE9_FINAL=$(curl --fail-with-body -sS -X POST "$API/agent/sessions/${PHASE9_SESSION_ID}/finalize")
echo "$PHASE9_FINAL" | python3 -c 'import sys,json; data=json.load(sys.stdin); assert data["status"] == "finalized"'
echo "    OK"

echo "  Hook and adapter assets..."
for asset in \
    "hooks/claude/session-start.sh" \
    "hooks/claude/pre-tool-use.sh" \
    "hooks/claude/post-tool-use.sh" \
    "hooks/claude/pre-compact.sh" \
    "hooks/claude/stop.sh" \
    "hooks/claude/session-end.sh" \
    "hooks/claude/install-hooks.sh" \
    "adapters/codex/datum-codex-wrapper.sh"; do
    [ -x "$REPO_DIR/$asset" ] || { echo "    FAIL: $asset missing or not executable"; exit 1; }
done
[ -f "$REPO_DIR/adapters/codex/AGENTS.md.template" ] || { echo "    FAIL: adapters/codex/AGENTS.md.template missing"; exit 1; }
echo "    OK"
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
