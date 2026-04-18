# Phase 0 Engineering Spec: Scope Lock And Implementation Contract

## Objective

Convert the approved project workflow designs into a concrete implementation
contract before any code changes begin.

## Inputs

- Approved Figma screens in file `mO9DPr3qC7AbQTpJqHiTGu`
- Existing project APIs in [backend/datum/api/projects.py](../backend/datum/api/projects.py)
- Existing shell and routing code in:
  - [frontend/src/router.tsx](../frontend/src/router.tsx)
  - [frontend/src/components/Layout.tsx](../frontend/src/components/Layout.tsx)
  - [frontend/src/components/CommandPalette.tsx](../frontend/src/components/CommandPalette.tsx)
  - [frontend/src/lib/route-project.ts](../frontend/src/lib/route-project.ts)

## Deliverables

1. A route matrix for project switching and fallback behavior.
2. A component inventory for all new or changed surfaces.
3. A data ownership map for project list, workspace, recents, and pins.
4. A release boundary table separating Release A from deferred work.
5. A test scenario list to drive implementation and validation.

## Route Preservation Contract

When switching from project `A` to project `B`, apply these rules:

| Current route | Target route |
| --- | --- |
| `/projects/A` | `/projects/B` |
| `/projects/A/inbox` | `/projects/B/inbox` |
| `/projects/A/sessions` | `/projects/B/sessions` |
| `/search?project=A&...` | `/search?project=B&...` |
| `/search?...` with no project | preserve global search route |
| `/projects/A/docs/*` | `/projects/B` |
| `/projects/A/docs/*/history` | `/projects/B` |
| unknown or unmappable project-scoped route | `/projects/B` |

Notes:

- Preserve the section only when the destination section is meaningful without
  the original document/entity identity.
- Document-specific routes do not map across projects in Release A.
- If there is no selected project, the app entry point is `/`.

## Screen To Component Mapping

| Figma | Target route or surface | Primary component |
| --- | --- | --- |
| NX 11 | `/` | `ProjectsHome` |
| NX 12 | Header overlay | `ProjectSwitcher` |
| NX 13 | Global modal | `CreateProjectModal` |
| NX 14 | `/` empty state | `ProjectsHomeEmptyState` |
| NX 15 | Global palette | `CommandPalette` updates |
| NX 16 | `/projects/:slug` zero-content state | `ProjectDashboard` updates |
| NX 17 | `/search` | `SearchPage` and `SearchResults` updates |
| NX 18 | `/projects/:slug/settings` | `ProjectSettingsPage` |

## Data Ownership

### Backend-owned

- canonical project list
- canonical project metadata
- project workspace snapshot
- search results and scope filters

### Frontend-owned in Release A

- recent projects
- pinned projects
- last-opened project for resume behavior
- switcher open/close state
- create-project modal open/close state

Recommendation:

- Persist recents, pins, and resume metadata in local storage for Release A.
- Do not create backend persistence for these until proven necessary.

## Release A Scope

- Projects Home
- Project Switcher
- Create Project modal
- New-project dashboard state
- Command palette project actions
- Search scope launch rules
- Read-only settings page

## Deferred From Release A

- editable settings
- rename/archive/delete behavior
- backend mutation for project metadata
- backend persistence for recents or pins

## Acceptance Criteria

- Every flow in the route contract is unambiguous.
- Every Figma artifact has a concrete route or component owner.
- Every local-only state is explicitly identified as frontend-owned.
- No Release B work is accidentally required to ship Release A.

## Implementation Gate

Phase 1 cannot start until the route contract above is treated as binding.
