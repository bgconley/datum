# Datum UAT Readiness

## Environment Assumptions

- Local validation was run from the repository workspace on macOS.
- Backend/unit validation assumes Python environments are available under:
  - `datum/backend/.venv`
  - `datum/qwen3-embedder-service/.venv`
  - `datum/qwen3-reranker-service/.venv`
  - `datum/gliner-ner-service/.venv`
- The repo-local compose profile assumes:
  - ParadeDB is started via `docker compose`
  - external model services are reachable from containers at
    `host.docker.internal:8010`, `:8011`, and `:8012`
- The GPU-node integration script is intentionally not a local-mac smoke test.
  It expects `/tank/...` paths, Docker services, and GPU-hosted model services.

## Commands Run

| Command | Result |
|---|---|
| `uv run --directory datum/backend ruff check datum tests` | PASS |
| `uv run --directory datum/backend mypy datum` | PASS |
| `uv run --directory datum/backend pytest -q` | PASS (`372 passed`) |
| `uv run --directory datum/backend pytest -q tests/test_document_manager.py tests/test_search.py tests/test_portable_bundle.py tests/test_api.py -q` | PASS |
| `npm run --prefix datum/frontend typecheck` | PASS |
| `npm run --prefix datum/frontend build` | PASS |
| `docker compose -f datum/docker-compose.yml config` | PASS |
| `uv run --directory datum/qwen3-embedder-service pytest -q` | PASS (`40 passed`) |
| `uv run --directory datum/qwen3-reranker-service pytest -q` | PASS (`60 passed`) |
| `uv run --directory datum/gliner-ner-service pytest -q` | PASS (`2 passed`) |

## What Was Verified Automatically

- Document delete now archives canonical files and records delete head events.
- Document rename/move now records new-path save and old-path delete lifecycle truth.
- API-boundary normalization prevents raw-path versus canonical-path drift on
  create/save/move/delete.
- Search accepts and routes `snapshot:<name>` and `branch:<name>` scopes.
- Search chunk hydration honors historical path overrides for temporal scopes.
- Portable bundle export/import preserves docs, attachments, blobs, `.piq`,
  snapshots, and branches metadata.
- Folder rename/delete and attachment move/delete are exposed through backend
  APIs and covered by regression tests.
- Compose now enforces restart/readiness behavior for UAT services.
- The app root now has a React error boundary instead of failing to a blank page.

## Manual Smoke Steps

1. Start the stack with `docker compose -f datum/docker-compose.yml up -d`.
2. Create a project and two docs in the UI.
3. Rename one doc, then search it with:
   - `current`
   - `all`
   - `as_of`
   - `branch:main`
4. Create a folder, move docs into it, rename the folder, then delete the folder.
5. Upload an attachment, move it, then delete it. Confirm the UI updates and the
   blob remains present under the configured blob root.
6. Trigger a deliberate frontend error in dev tooling or inspect browser console
   while navigating; confirm the app renders the root error fallback instead of a blank page.
7. From the CLI, run:
   - `datum export <project-slug> --output /tmp/<project-slug>-bundle`
   - `datum import /tmp/<project-slug>-bundle`
   - Confirm the imported project appears and its docs are searchable.

## Residual Non-Blocking Risks

- `medium`: Browser-driven E2E automation was not run in this closure pass.
  The React build and targeted API regressions are green, but final UX still
  relies on the manual smoke above.
- `low`: The local pass did not run `scripts/integration-test.sh` because this
  machine does not provide the GPU-node prerequisites the script requires.
  That script should still be executed on the target `/tank/...` environment
  before production promotion.
- `low`: Frontend production bundles remain large in the PDF/Mermaid/editor
  areas. This is not a UAT blocker, but it remains worth monitoring.
