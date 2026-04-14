# Datum Spec Conformance (HEAD)

This file is the authoritative spec-conformance matrix for the current
repository `HEAD`.

Use this file together with [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md)
when evaluating readiness. Per-phase implementation plans under
`../docs/plans/` are point-in-time phase-boundary docs; deferred items there are
historical unless still listed here as open.

## Scope For This Conformance Matrix

- Included: functional behavior, data model, pipeline orchestration, operability.
- Out of scope by project decision: PII/security hardening/model-endpoint auth
  controls for private-network deployments (tracked separately in
  `SECURITY_ASSUMPTIONS.md`).

## Phase Matrix

| Phase | Design Intention | Implemented Surface (HEAD) | Conformance |
|---|---|---|---|
| 1 | Filesystem-canonical cabinet, versioned docs, reconciler authority | `backend/datum/services/{project_manager,document_manager,versioning,reconciler,doctor}.py`; migration `001_initial_schema.py` | Complete |
| 2 | Ingestion/search foundation: extraction, chunking, embeddings, hybrid retrieval | `backend/datum/services/{extraction,chunking,technical_terms,ingestion,search,model_gateway}.py`; APIs `api/search.py`; migrations `002`, `003`, `004` | Complete |
| 3 | Evaluation/re-embedding/reranking with provenance and idempotency | `backend/datum/services/{evaluation,reembedding,reranking,pipeline_configs,idempotency}.py`; APIs `api/evaluation.py`; migration `005` | Complete |
| 4 | Frontend source-first workspace with robust search/editor/history UX | `frontend/src/{router.tsx,App.tsx}` + workspace/search components under `frontend/src/components/`; API integration via `frontend/src/lib/api.ts` | Complete |
| 5 | Entity/candidate intelligence with curated acceptance flow | `backend/datum/services/{entity_extraction,candidate_extraction,llm_candidates,entities,intelligence}.py`; APIs `api/{entities,inbox}.py`; migration `006` | Complete |
| 6 | Agent context/citation/MCP/session workflow | `backend/datum/services/{context,citations,sessions,api_keys}.py`; APIs `api/{context,citations,sessions,admin}.py`; `backend/datum/mcp_server.py`; migration `007` | Complete |
| 7 | Intelligence graph: links, relationships, insights, traceability | `backend/datum/services/{link_detection,llm_relationships,traceability,insight_analysis,staleness,contradiction}.py`; APIs `api/traceability.py`; migration `008` | Complete |
| 8 | Operational UX/data layer: saved searches, collections, annotations, attachments, GC/doctor/backup flows | APIs `api/{saved_searches,collections,annotations,upload,filesystem,templates}.py`; services `blob_{store,gc}.py`; scripts `scripts/{backup.sh,restore-drill.sh,snapshot-policy.sh,integration-test.sh}`; migration `009` | Complete |
| 9 | Lifecycle enforcement for agent writes and adapters | `backend/datum/services/{write_barrier,stop_barrier,delta_aggregator,session_state}.py`; API `api/lifecycle.py`; hooks `hooks/claude/*`; codex adapter `adapters/codex/*`; migration `010` | Complete |

## Cross-Phase Conformance Notes

- Embedding contract is fixed to `1024` dimensions at schema/service level,
  aligned with the design's Datum v1 Matryoshka contract:
  - DB schema: `halfvec(1024)`
  - worker/gateway/search call path requests/uses `1024` directly
- Search result assembly now uses batched hydration in
  `backend/datum/services/search.py` to avoid N+1 query patterns.
- Integration/operational scripts are tested for stream correctness and teardown
  safety (`backend/tests/test_operational_scripts.py`).

## Verification Anchors

- Backend quality gates:
  - `uv run ruff check datum tests`
  - `uv run mypy datum`
  - `uv run pytest -q`
- Frontend quality gates:
  - `npm run typecheck`
  - `npm run build`
- Runtime/integration:
  - `docker compose config`
  - `bash scripts/integration-test.sh` (GPU node canonical run)
