# Datum Implementation Status

This repository tracks the full Datum roadmap (Phase 1 through Phase 9), but
the code at current `HEAD` intentionally reflects a subset of that roadmap.

## Current Delivery State

- Implemented and validated locally: **Phase 1 through Phase 7**
- Planned and outstanding: **Phase 8 through Phase 9**

## What This Means Operationally

- The design and per-phase plans for Phases 8-9 remain authoritative planning
  documents, not a statement that those phases are already live at `HEAD`.
- Audits and implementation reviews must evaluate shipped behavior against the
  implemented phase set unless explicitly running a future-phase review.

## Database Schema Marker

- Current migration head in this repo includes Phase 7
  (`008_phase7_intelligence_graph.py`).
- Intelligence-graph tables `document_links`, `entity_relationships`, and
  `insights` now exist at `HEAD`.
- Phase 7 operator workflow includes `datum insights analyze <project>` and
  `datum insights list <project>`.
- Future-phase operational tables such as `agent_sessions` and
  `session_deltas` remain Phase 9 work.

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
