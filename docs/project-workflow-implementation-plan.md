# Project Workflow Implementation Plan

## Purpose

This document defines the phased execution plan for implementing the approved
project workflow work in Datum. It converts the Figma-approved UX into an
engineering sequence with explicit dependencies, phase boundaries, and exit
criteria.

Approved Figma artifacts live in file `mO9DPr3qC7AbQTpJqHiTGu`:

- `NX 11 — Projects Home`
- `NX 12 — Project Switcher`
- `NX 13 — Create Project Modal`
- `NX 14 — Projects Empty State`
- `NX 15 — Command Palette (Projects)`
- `NX 16 — Dashboard (New Project)`
- `NX 17 — Search Results (Project Scope)`
- `NX 18 — Project Settings`

## Goals

- Make projects a first-class workflow in the web app, not just a URL pattern.
- Support project creation, opening, switching, and scoped search end to end.
- Preserve route context when switching projects wherever it is logically safe.
- Keep implementation aligned to the approved Figma states and flows.
- Validate on the GPU-node runtime against live services before declaring done.

## Current Baseline

Existing backend support:

- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{slug}`
- `GET /api/v1/projects/{slug}/workspace`
- `WS /ws/projects/{slug}/workspace`

Relevant code:

- [backend/datum/api/projects.py](../backend/datum/api/projects.py)
- [frontend/src/components/CreateProjectDialog.tsx](../frontend/src/components/CreateProjectDialog.tsx)
- [frontend/src/components/Layout.tsx](../frontend/src/components/Layout.tsx)
- [frontend/src/components/CommandPalette.tsx](../frontend/src/components/CommandPalette.tsx)
- [frontend/src/router.tsx](../frontend/src/router.tsx)
- [frontend/src/lib/route-project.ts](../frontend/src/lib/route-project.ts)

Current gaps:

- `/` is still a placeholder marketing/build screen.
- The header chip is not a switcher; it is just a link back to the dashboard.
- The command palette filters project actions down to the currently selected
  project.
- Project creation exists but is not exposed as a first-class global workflow.
- Search scope behavior exists in the route model, but launch behavior is not
  yet standardized.
- Project settings are only a design artifact today.

## Phase Overview

### Phase 0

Scope lock and implementation spec.

See: [project-workflow-phase-0-scope-lock.md](./project-workflow-phase-0-scope-lock.md)

### Phase 1

Navigation and route foundation.

See: [project-workflow-phase-1-navigation-foundation.md](./project-workflow-phase-1-navigation-foundation.md)

### Phase 2

Project creation workflow and post-create onboarding.

See: [project-workflow-phase-2-project-creation.md](./project-workflow-phase-2-project-creation.md)

### Phase 3

Command palette and search behavior for cross-project workflows.

See: [project-workflow-phase-3-command-search.md](./project-workflow-phase-3-command-search.md)

### Phase 4

Project settings surface within current backend capabilities.

See: [project-workflow-phase-4-project-settings.md](./project-workflow-phase-4-project-settings.md)

### Phase 5

GPU-node deployment and validation.

See: [project-workflow-phase-5-validation.md](./project-workflow-phase-5-validation.md)

## Execution Order

1. Complete Phase 0 and treat it as the implementation contract.
2. Implement Phase 1 before any project-creation or search work.
3. Implement Phase 2 once routing and project switching primitives are stable.
4. Implement Phase 3 after the create/open/switch model is in place.
5. Implement Phase 4 after the shell is stable.
6. Execute Phase 5 only after local and GPU-node code paths are ready.

## Release Boundaries

### Release A

Ship the operational project workflow:

- Projects Home
- Project Switcher
- Create Project modal and landing behavior
- Post-create onboarding dashboard state
- Command palette project actions
- Search launch defaults and visible scope behavior
- Route preservation and deterministic fallback behavior
- Read-only project settings surface

### Release B

Optional backend-backed mutation support for project settings:

- edit metadata
- rename
- archive
- delete

Release B requires explicit backend/API expansion and should not be implicitly
bundled into Release A.

## Out Of Scope

The following remain explicitly excluded from this implementation plan:

- permissions and roles
- multi-user ownership
- project templates at creation time
- import/export/clone project flows

## Global Acceptance Criteria

- Every implemented screen maps directly to an approved Figma artifact.
- Project creation, opening, and switching work without shell breakage.
- Cross-project navigation preserves context when logically valid.
- Search defaults are predictable and visible to the user.
- The command palette supports true cross-project work.
- GPU-node validation passes against the real inference topology.

## Stop Conditions

Stop and regroup before implementation if any of the following become true:

- Figma artifacts require structural change rather than implementation detail.
- The route-preservation model proves ambiguous in real use.
- The backend must expand materially beyond the agreed Release A surface.
- GPU-node runtime assumptions diverge from the expected service topology.
