# Phase 3 Engineering Spec: Command Palette And Search For Cross-Project Work

## Objective

Make the command palette and search model consistent with multi-project
navigation and scope selection.

## Existing Anchors

- [frontend/src/components/CommandPalette.tsx](../frontend/src/components/CommandPalette.tsx)
- [frontend/src/components/SearchPage.tsx](../frontend/src/components/SearchPage.tsx)
- [frontend/src/components/SearchResults.tsx](../frontend/src/components/SearchResults.tsx)
- [frontend/src/lib/search-route.ts](../frontend/src/lib/search-route.ts)

## Current Problems

- The command palette limits visible projects to the current project when one is
  selected.
- Search scope exists in route state but launch behavior is not standardized.
- Global search and project-scoped search are not clearly separated in the
  action model.

## Required Changes

### 1. Remove current-project-only filtering in the palette

Current logic in [CommandPalette.tsx](../frontend/src/components/CommandPalette.tsx)
filters projects down to the selected project.

Release A behavior:

- always show project navigation results across all projects
- document results may still be filtered or grouped as appropriate
- project actions remain available from any shell

### 2. Add explicit project actions

The palette should support:

- open project
- create project
- open Projects Home
- search all projects

Optional in Release A:

- reopen recent project in same section

### 3. Standardize search-launch defaults

When search is launched from a project shell:

- default `draft.project` to that project slug

When search is launched from Projects Home or a global action:

- default to no project filter

### 4. Preserve search route state on project switch

When switching projects from a search route:

- preserve query
- preserve mode
- preserve version scope
- replace `project` in route state with the new slug

If search is global with no project filter:

- remain global unless the user explicitly chose a project-scoped switch action

## UI And State Contract

### Command palette

- navigation-first
- no settings-heavy actions in the primary set
- project results are globally accessible

### Search

- visible distinction between current-project and all-project scope
- switching scope does not clear query state
- current-project search is the default only when launched from project context

## Acceptance Criteria

- Command palette can open any project from any route.
- Command palette can create a project.
- Command palette can launch global search.
- Search launched from project context defaults to that project.
- Search launched from global context defaults to all projects.
- Search route remains stable when switching project scope.

## Tests

### Unit

- search draft initialization from route context
- project-switch transformation for search routes

### Integration

- open another project from palette while already inside a project
- create project from palette
- launch search from project dashboard and confirm scoped default
- launch search from Projects Home and confirm global default
- switch project while on search and confirm query preservation

## Risks

- palette becomes overloaded with actions
- project-scoped and global search rules diverge between components

Mitigation:

- centralize search launch helpers
- keep the palette biased toward navigation and creation, not settings
