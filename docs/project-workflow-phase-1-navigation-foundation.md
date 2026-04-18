# Phase 1 Engineering Spec: Navigation And Route Foundation

## Objective

Establish projects as a first-class navigation model in the app shell.

## User Outcomes

- A user can open the app at `/` and see a real Projects Home.
- A user can switch projects from the header without losing the shell.
- The app preserves context when switching between dashboard, inbox, sessions,
  and search.
- The app falls back predictably when the current route cannot map.

## Existing Anchors

- [frontend/src/router.tsx](../frontend/src/router.tsx)
- [frontend/src/components/Layout.tsx](../frontend/src/components/Layout.tsx)
- [frontend/src/lib/route-project.ts](../frontend/src/lib/route-project.ts)
- [frontend/src/lib/workspace-query.ts](../frontend/src/lib/workspace-query.ts)

## New Or Updated Components

### New

- `ProjectsHome`
- `ProjectSwitcher`
- `useProjectNavigation` or equivalent route helper
- `project-preferences` helper for recents/pins/resume state

### Updated

- `router.tsx`
- `Layout.tsx`
- `Sidebar.tsx`

## Required Changes

### 1. Replace the root placeholder route

Current root content in [router.tsx](../frontend/src/router.tsx) is a
placeholder build screen. Replace it with `ProjectsHome`.

Behavior:

- if projects exist, render the indexed project home
- if no projects exist, render the empty state variant

### 2. Add a project navigation helper

Add a helper that accepts:

- current pathname
- current search string
- destination project slug

It returns:

- destination route path
- destination search state

Responsibilities:

- detect current route section
- preserve section where allowed
- remap project-scoped search routes
- fall back to `/projects/:slug` for document/history routes

### 3. Replace the fake header chip link

Current behavior in [Layout.tsx](../frontend/src/components/Layout.tsx) renders
`{selectedProject} ▾` as a dashboard link. Replace it with:

- a button or trigger
- overlay open state
- switcher selection behavior using the navigation helper

### 4. Add frontend project preferences

Persist the following in local storage:

- recent projects with last-opened timestamp
- pinned project slugs
- last-opened project slug for resume

These values drive:

- Projects Home resume card
- Projects Home recent/pinned sections
- Project Switcher grouping

## Data Flow

- Project list comes from `useProjectsQuery()`.
- Project workspace remains project-specific via `useProjectWorkspaceQuery()`.
- Recents/pins are local-only and merged into the displayed list on the client.

## Acceptance Criteria

- `/` renders a project index instead of placeholder copy.
- Header project chip opens a real switcher overlay.
- Switching from dashboard, inbox, sessions, and search preserves section.
- Switching from a document route falls back to the destination project
  dashboard.
- Recent/pinned state survives reload in the same browser.

## Tests

### Unit

- route mapping helper
- recents/pins local-storage state
- selected-project derivation

### Integration

- open app at `/`
- open a project from home
- switch projects from dashboard
- switch projects from inbox
- switch projects from sessions
- switch projects from search
- switch projects from a document route and verify fallback

## Risks

- route preservation logic becoming too implicit
- shell state drifting between header, sidebar, and router

Mitigation:

- keep all project-switch routing decisions in one helper
- do not duplicate route-preservation logic across components
