# Datum Implementation Status

This repository tracks the full Datum roadmap (Phase 1 through Phase 9), but
the code at current `HEAD` intentionally reflects a subset of that roadmap.

## Current Delivery State

- Implemented and validated locally: **Phase 1 through Phase 8**
- Planned and outstanding: **Phase 9**

## What This Means Operationally

- The design and per-phase plan for Phase 9 remains an authoritative planning
  document, not a statement that Phase 9 is already live at `HEAD`.
- Audits and implementation reviews should treat Phase 8 as shipped behavior
  and Phase 9 as future work unless a forward-looking review is explicitly requested.

## Database Schema Marker

- Current migration head in this repo includes Phase 8
  (`009_phase8_operational_tables.py`).
- Phase 8 operational tables `saved_searches`, `collections`,
  `collection_members`, `annotations`, and `attachments` now exist at `HEAD`.
- Phase 8 operator workflow includes `datum doctor ...`, `datum gc ...`, and
  `scripts/backup.sh`, `scripts/restore-drill.sh`, `scripts/snapshot-policy.sh`.
- Future-phase lifecycle tables such as `agent_sessions` and `session_deltas`
  remain Phase 9 work.

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
