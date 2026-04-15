# Datum Spec Conformance

This file records current `HEAD` conformance against the design doc for the
surfaces that were disputed during UAT closure.

## Phase Summary

| Phase | Status | Evidence |
|---|---|---|
| 1 | Complete | filesystem-canonical cabinet, versioning, reconciler, doctor |
| 2 | Complete | ingestion/search pipeline, hybrid retrieval, worker/model gateway |
| 3 | Complete | eval, reranking, re-embedding, pipeline configs, idempotency |
| 4 | Complete | TanStack Router frontend, source-first workspace, history/search UX |
| 5 | Complete | inbox, candidates, entities, curated records |
| 6 | Complete | context, citations, sessions, API keys, MCP server |
| 7 | Complete | links, relationships, traceability, insights |
| 8 | Complete | saved searches, collections, annotations, uploads, GC/doctor/backup |
| 9 | Complete | lifecycle enforcement, adapters, hook integration |

## UAT-Critical Requirement Matrix

| Requirement | Before | After | Evidence |
|---|---|---|---|
| Filesystem-canonical document lifecycle with temporal head events | Partial | Complete | `backend/datum/services/{document_manager,manifest_history,versioning,db_sync}.py`; tests `test_document_manager.py::TestLifecycleSemantics`, `test_api.py::test_move_document_endpoint`, `test_api.py::test_delete_document_endpoint_soft_deletes_and_archives` |
| Delete closes prior head and preserves historical reconstruction | Partial | Complete | manifest `head_events` now record delete transitions; derived `version_head_events` rebuilt/synced with `canonical_path`; tests above plus `test_search.py::test_term_search_applies_as_of_scope` |
| Rename/move modeled as old-path delete plus new-path save | Violated | Complete | `move_document()` now creates a new head at the new path and appends old-path delete history; DB sync emits both save/delete truth; tests `test_move_records_temporal_head_events`, `test_move_document_endpoint` |
| Canonical-path normalization at API boundary | Partial | Complete | document/filesystem delete+rename routes normalize before DB sync/audit; tests `test_move_document_db_sync_uses_normalized_canonical_path`, `test_delete_document_db_sync_uses_normalized_canonical_path`, existing create/save normalization tests |
| Version-aware search scopes `current`, `all`, `as_of`, `snapshot`, `branch` | Partial | Complete | `backend/datum/schemas/search.py`, `backend/datum/services/search.py`, `frontend/src/{lib/search-route.ts,components/SearchBar.tsx,components/SearchPage.tsx,router.tsx}`; tests `test_search_accepts_snapshot_and_branch_scopes`, `test_term_search_applies_branch_scope`, `test_term_search_applies_snapshot_scope`, `test_prefetch_search_chunks_applies_path_overrides` |
| Portable Appendix B `datum export` / `datum import` | Missing | Complete | `backend/datum/cli/{main,portable}.py`, `backend/datum/services/portable_bundle.py`; tests `test_export_import_round_trip_preserves_bundle_layout_and_files`, `test_import_bundle_reports_rebuilt_db_state_when_requested`, `test_root_cli_dispatches_portable_commands` |
| Folder rename/delete lifecycle | Missing | Complete | `backend/datum/services/document_manager.py`, `backend/datum/api/documents.py`, `frontend/src/components/Sidebar.tsx`; tests `test_folder_rename_decomposes_into_document_moves`, `test_folder_delete_decomposes_into_document_deletes`, `test_rename_folder_endpoint_moves_documents`, `test_delete_folder_endpoint_archives_documents` |
| Attachment move/delete lifecycle with blob retention | Missing | Complete | `backend/datum/services/attachment_manager.py`, `backend/datum/api/{upload,attachments}.py`, `frontend/src/components/Sidebar.tsx`; test `test_attachment_lifecycle_endpoints` |
| UAT runtime resilience: restart policies, readiness gates, root error boundary, sync visibility | Partial | Complete | `docker-compose.yml`, `backend/datum/watcher.py`, `backend/datum/services/project_versioning.py`, `backend/datum/api/versions.py`, `backend/datum/services/reconciler.py`, `frontend/src/App.tsx` |

## Validation Anchors

- Backend: `uv run --directory datum/backend ruff check datum tests`
- Backend: `uv run --directory datum/backend mypy datum`
- Backend: `uv run --directory datum/backend pytest -q`
- Frontend: `npm run --prefix datum/frontend typecheck`
- Frontend: `npm run --prefix datum/frontend build`
- Infra: `docker compose -f datum/docker-compose.yml config`
- Model services:
  - `uv run --directory datum/qwen3-embedder-service pytest -q`
  - `uv run --directory datum/qwen3-reranker-service pytest -q`
  - `uv run --directory datum/gliner-ner-service pytest -q`

See [`./UAT_READINESS.md`](./UAT_READINESS.md) for command results, assumptions,
manual smoke steps, and residual non-blocking risks.
