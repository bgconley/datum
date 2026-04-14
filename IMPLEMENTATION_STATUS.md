# Datum Implementation Status

This repository tracks the full Datum roadmap (Phase 1 through Phase 9), and
the code at current `HEAD` implements the full Phase 1-9 delivery surface.

## Current Delivery State

- Implemented and validated locally: **Phase 1 through Phase 9**

## What This Means Operationally

- The design and per-phase plan for Phase 9 is now implemented at `HEAD`.
- Audits and implementation reviews should treat Phase 9 as active behavior.

## Database Schema Marker

- Current migration head in this repo includes Phase 9
  (`010_phase9_lifecycle_tables.py`).
- Phase 8 operational tables `saved_searches`, `collections`,
  `collection_members`, `annotations`, and `attachments` now exist at `HEAD`.
- Phase 8 operator workflow includes `datum doctor ...`, `datum gc ...`, and
  `scripts/backup.sh`, `scripts/restore-drill.sh`, `scripts/snapshot-policy.sh`.
- Phase 9 lifecycle tables `agent_sessions` and `session_deltas` now exist at `HEAD`.
- Phase 9 active runtime surfaces also include:
  - `/api/v1/agent/sessions/*`
  - lifecycle write barrier / stop barrier enforcement
  - `hooks/claude/*`
  - `adapters/codex/*`

## Canonical References

- Current conformance matrix (authoritative at `HEAD`):
  - `./SPEC_CONFORMANCE.md`
- Design: `../docs/plans/2026-04-10-datum-design.md`
- Phase plans:
  - `../docs/plans/2026-04-10-datum-phase1-implementation.md`
  - `../docs/plans/2026-04-10-datum-phase2-implementation.md`
  - `../docs/plans/2026-04-10-datum-phase3-implementation.md`
  - `../docs/plans/2026-04-10-datum-phase4-implementation.md`
  - `../docs/plans/2026-04-10-datum-phase5-implementation.md`
  - `../docs/plans/2026-04-11-datum-phase6-implementation.md`
  - `../docs/plans/2026-04-11-datum-phase7-implementation.md`
  - `../docs/plans/2026-04-11-datum-phase8-implementation.md`
  - `../docs/plans/2026-04-11-datum-phase9-implementation.md`

## Spec-Conformance Interpretation Rule

- The per-phase implementation plans are point-in-time contracts for each
  phase boundary.
- "Deferred" items in earlier phase plans are expected and are superseded by
  later phases when implemented.
- For current `HEAD`, use `SPEC_CONFORMANCE.md` plus this file to determine
  whether behavior is aligned with the design doc.
