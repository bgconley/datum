# Datum Implementation Status

Current `HEAD` implements the Phase 1-9 runtime plus the previously missing
design appendix surfaces that were blocking UAT.

## Current Delivery State

- Implemented and validated locally: Phase 1 through Phase 9
- UAT-closure work completed at `HEAD`:
  - lifecycle-correct document delete and rename/move semantics
  - canonical-path normalization at API boundaries for derived DB/audit sync
  - portable `datum export` / `datum import`
  - snapshot and branch search scopes
  - folder rename/delete lifecycle flows
  - attachment move/delete lifecycle flows
  - compose restart/health/readiness hardening and app-root error boundary

## Database Schema Marker

- Current migration head: `011_version_head_event_canonical_path.py`
- `version_head_events` now records `canonical_path` so temporal reconstruction
  can return the correct historical cabinet path for `as_of`, `snapshot`, and
  `branch` search scopes.

## Operator Interpretation

- Filesystem remains canonical.
- Postgres/search/intelligence remain derived and rebuildable from cabinet state.
- The default UAT compose profile now runs lifecycle enforcement in
  `blocking` mode and adds restart/readiness behavior for `datum-api`,
  `datum-worker`, and `datum-watcher`.

## Canonical References

- Conformance matrix: [`./SPEC_CONFORMANCE.md`](./SPEC_CONFORMANCE.md)
- Operator handoff and validation log: [`./UAT_READINESS.md`](./UAT_READINESS.md)
- Agent contract: [`./AGENTS.md`](./AGENTS.md)
- Design: `../docs/plans/2026-04-10-datum-design.md`
