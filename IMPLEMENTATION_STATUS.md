# Datum Implementation Status

This repository tracks the full Datum roadmap (Phase 1 through Phase 9), but
the code at current `HEAD` intentionally reflects a subset of that roadmap.

## Current Delivery State

- Implemented and validated: **Phase 1 through Phase 6**
- Planned and outstanding: **Phase 7 through Phase 9**

## What This Means Operationally

- The design and per-phase plans for Phases 7-9 are authoritative planning
  documents, not a statement that those phases are already live at `HEAD`.
- Audits and implementation reviews must evaluate shipped behavior against the
  implemented phase set unless explicitly running a future-phase review.

## Database Schema Marker

- Current migration head in this repo is Phase 6 era (`007_agent_api_keys_idempotency.py`).
- Future-phase tables such as `document_links`, `entity_relationships`,
  `insights`, `agent_sessions`, and `session_deltas` are expected only after
  Phases 7-9 are implemented.

## Canonical References

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
