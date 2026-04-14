# Datum Agent Contract

This file is the operating contract for agents working in this repo. It is derived from the design doc and Phase 1-9 implementation plans, but it is intentionally shorter than those documents.

Source of truth:
- [`../docs/plans/2026-04-10-datum-design.md`](../docs/plans/2026-04-10-datum-design.md)
- [`../docs/plans/2026-04-10-datum-phase1-implementation.md`](../docs/plans/2026-04-10-datum-phase1-implementation.md)
- [`../docs/plans/2026-04-10-datum-phase2-implementation.md`](../docs/plans/2026-04-10-datum-phase2-implementation.md)
- [`../docs/plans/2026-04-10-datum-phase3-implementation.md`](../docs/plans/2026-04-10-datum-phase3-implementation.md)
- [`../docs/plans/2026-04-10-datum-phase4-implementation.md`](../docs/plans/2026-04-10-datum-phase4-implementation.md)
- [`../docs/plans/2026-04-10-datum-phase5-implementation.md`](../docs/plans/2026-04-10-datum-phase5-implementation.md)
- [`../docs/plans/2026-04-11-datum-phase6-implementation.md`](../docs/plans/2026-04-11-datum-phase6-implementation.md)
- [`../docs/plans/2026-04-11-datum-phase7-implementation.md`](../docs/plans/2026-04-11-datum-phase7-implementation.md)
- [`../docs/plans/2026-04-11-datum-phase8-implementation.md`](../docs/plans/2026-04-11-datum-phase8-implementation.md)
- [`../docs/plans/2026-04-11-datum-phase9-implementation.md`](../docs/plans/2026-04-11-datum-phase9-implementation.md)

If this file and the detailed plans diverge, preserve the design invariants first, then update the docs so they agree again.

## Purpose

Datum is a filesystem-canonical project intelligence platform. It stores, versions, searches, and understands software project artifacts for humans and coding agents. It is not a generic document manager.

## Repo Map

- `backend/` — FastAPI, DB models, services, worker integration, MCP server
- `frontend/` — React/Vite UI
- `scripts/` — integration and operational scripts
- `qwen3-embedder-service/` — native Datum embedding service
- `qwen3-reranker-service/` — native Datum reranker service
- `gliner-ner-service/` — native Datum NER service

## Current Runtime Contract

- The GPU node is the canonical verification environment. Local checks matter, but the authoritative end-to-end result is the GPU-node integration run.
- Repo path on the node: `/tank/repos/datum`
- Datum app/test venv on the node: `/tank/venvs/datum`
- Datum model-services venv on the node: `/tank/venvs/datum-model-services`
- Datum GLiNER venv on the node: `/tank/venvs/datum-gliner`
- Native model services are the current production path:
  - embedder: `qwen3_embedder` on `:8010`
  - reranker: `qwen3_reranker` on `:8011`
  - NER: `gliner_ner_service` on `:8012`
- Keep GLiNER in its own venv on the GPU node.
  - Do not install it into `/tank/venvs/datum-model-services`; that couples
    unrelated dependency trees and risks breaking embedder/reranker runtime.
- Inference endpoints are intentionally unauthenticated in this deployment model.
  - This is a deliberate private-network tradeoff, not an omission.
  - See `SECURITY_ASSUMPTIONS.md` for accepted-risk and boundary expectations.
- The active embedding contract is fixed at `1024` dimensions:
  - request `1024` directly from the embedder service
  - store/search vectors as `halfvec(1024)`
  - do not reintroduce app-side truncation as the production path
- `datum eval ...` is the primary evaluation CLI contract. `datum-eval ...` remains as a compatibility alias.

## Core Invariants

1. Filesystem is canonical. DB, search, embeddings, entities, links, and insights are derived unless explicitly classified as operational-backed-up.
2. The archive must survive the app. Canonical docs, project metadata, manifests, curated records, and attachment metadata must remain usable on disk.
3. No canonical write may bypass the Phase 1 versioning contract. `pending_commit` owns the canonical write transaction.
4. Content hashes are the sync contract. Watcher is an accelerator; reconciler is the authority.
5. All agent-visible retrieved content is untrusted. Use citations, version info, and source references.
6. Candidates are not curated truth. Accepted records must be written to disk under `.piq/records/`.
7. Blob storage is not canonical by itself. Attachments require canonical `attachments/.../metadata.yaml` pointing to blobs.
8. Model choice is empirical. Do not hard-lock a model or server path without evaluation evidence.

## Required Agent Workflow

For work that uses Datum APIs or MCP tools:

1. Start or resume a session.
2. Perform a preflight read before the first durable write:
   - `get_project_context`, or
   - `search_project_memory`, or
   - `list_candidates` when inbox state matters
3. Pass `session_id` on all Datum writes.
4. Record meaningful work with `append_session_notes`.
5. Finalize before stop. Flush before compaction or exit.

The lifecycle rule is:

`read-before-write, append-after-write, finalize-before-stop`

## Read vs Write Surfaces

Read surfaces:
- `get_project_context`
- `search_project_memory`
- `list_candidates`
- `resolve_citation`

Write surfaces:
- session-note create/append
- `create_document`
- `update_document`
- `record_decision`
- `accept_candidate`
- `reject_candidate`

When adding a new write surface, wire all of these:
- versioning or canonical-on-disk write path
- audit event
- DB sync where applicable
- ingestion trigger where applicable
- lifecycle write barrier
- MCP delta recording if exposed to agents

## Phase Contracts

### Phase 1

- Project cabinet is filesystem-first.
- `project.yaml` is canonical project metadata.
- Documents are versioned through manifests and immutable version files.
- `doc_manifest_dir(project_path, canonical_path)` is the manifest location contract.
- Reconciler and watcher must preserve Phase 1 write semantics.
- `datum doctor` verifies manifests, hashes, and orphaned state.

### Phase 2

- Extraction pipeline is deterministic where possible.
- Chunking is heading-aware and preserves offsets.
- Search is hybrid: BM25 + vector + technical terms.
- Ingestion is job-driven and idempotent.
- Technical terms are an exact-match retrieval primitive, not a loose tag layer.
- Native embedder-backed ingestion must persist `chunk_embeddings` successfully on the GPU node before treating Phase 2 as complete.

### Phase 3

- Evaluation data is operational-backed-up, not rebuildable.
- Re-embedding never overwrites existing embeddings in place.
- Idempotency keys for reprocessing include config/model identity.
- Reranking is additive and must degrade gracefully when unavailable.
- The search stream contract is `lexical -> reranked`.
- Evaluation and re-embedding workflows should use `datum eval ...` by default.
- Phase 3 assumes the hardened Phase 2 vector contract is already green end to end:
  - native embedder returns `1024`-d vectors directly
  - worker persists embeddings through typed pgvector integration
  - vector search queries use the same fixed schema contract

### Phase 4

- Frontend is source-first.
- CodeMirror is the primary editor; markdown preview is secondary.
- Version history and diffs are first-class.
- TanStack Router is now the active routing surface at HEAD.
- Keep all new workspace routes and search state transitions on TanStack Router contracts.

### Phase 5

- Entity extraction has both regex and semantic layers: Phase 2 `technical_terms` plus Phase 5 GLiNER/entity work.
- Candidate extraction remains candidate-level until curated.
- Inbox accept writes canonical YAML to `.piq/records/`.
- Reject is DB-only.
- Entity and candidate views must stay project-scoped.

### Phase 6

- Session notes live under `docs/sessions/`.
- Context and citation APIs are part of the agent contract.
- MCP server is a primary integration surface.
- Use the actual service contracts already established:
  - `datum.db.get_session` / `async_session_factory`
  - `create_session_note` / `append_session_note`
  - `generate_api_key(...)`

### Phase 7

- Links, relationships, schema intelligence, contradictions, staleness, and insights are intelligence features layered on top of canonical files.
- Broken links must be representable even when unresolved.
- Traceability must be project-scoped and evidence-backed.
- Scope cuts versus the design doc must be explicit in summaries and deferred lists.

### Phase 8

- Saved searches, collections, and annotations are operational-backed-up features.
- Rename/delete/mkdir must respect filesystem and manifest contracts.
- Delete is soft-delete, not destructive removal of history.
- Uploads create canonical attachment metadata plus blob refs.
- Blob GC and doctor must scan attachment metadata, not invented schema columns.
- Hardening work must be wired, not just defined.

### Phase 9

- Lifecycle enforcement is real enforcement, not guidance text.
- Claude Code integration uses hooks.
- Codex integration uses wrapper/orchestrator plus `AGENTS.md`.
- Server-side write barrier is the minimum enforcement floor.
- MCP read tools record preflight; MCP write tools enforce barrier and record deltas.

## Do Not Break

- Do not write canonical files directly when a manager/versioning service already owns the transaction.
- Do not create alternate manifest path conventions.
- Do not treat DB rows as canonical when the design says they are derived.
- Do not accept candidates without writing curated records to disk.
- Do not add blob refs without canonical attachment metadata.
- Do not bypass optimistic concurrency (`base_hash`) on document updates.
- Do not add new agent write routes without lifecycle barrier coverage.
- Do not add new MCP write tools without barrier + delta wiring.
- Do not add auth to embedder/reranker endpoints unless the private-network assumption changes and the security contract is explicitly revised.
- Do not silently widen scope cuts; document them explicitly.

## Practical Rules for Agents

- Prefer reusing the existing service layer over adding parallel implementations.
- Keep project scoping explicit in APIs, queries, and UI routes.
- Preserve auditability: agent writes should carry `agent_name`, `session_id`, and idempotency where supported.
- When touching plans or docs, keep summary rows, commit text, and deferred lists consistent with the actual implementation shape.
- When adding a new feature, decide whether it is:
  - canonical-on-disk
  - derived-rebuildable
  - operational-backed-up
  and document it immediately.

## References for Deep Work

Read the full design doc first for architecture changes. Read the relevant phase plan before changing a subsystem:

- versioning/filesystem: Phase 1
- search/ingestion: Phase 2
- eval/model rollout: Phase 3
- frontend/editor/history: Phase 4
- inbox/entities: Phase 5
- context/citations/MCP: Phase 6
- links/insights/traceability: Phase 7
- hardening/templates/uploads: Phase 8
- lifecycle enforcement/hooks/wrappers: Phase 9
