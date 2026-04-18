# Phase 4 Engineering Spec: Project Settings Surface

## Objective

Implement the project settings screen in a way that is useful in Release A
without forcing premature backend expansion.

## Existing Anchors

- [backend/datum/schemas/project.py](../backend/datum/schemas/project.py)
- [backend/datum/api/projects.py](../backend/datum/api/projects.py)

Current backend capabilities:

- list project metadata
- create project
- get project metadata
- get workspace snapshot

Current backend limitations:

- no update endpoint
- no rename endpoint
- no archive endpoint
- no delete endpoint

## Release A Scope

Ship a real settings page that is:

- navigable
- project-aware
- visually aligned to Figma
- read-only for now, except for client-side navigation defaults if we choose to
  support them locally

## Required Changes

### 1. Add a real settings route

Recommended route:

- `/projects/:slug/settings`

### 2. Implement read-only sections

- General
  - name
  - slug
  - description
- Project metadata
  - status
  - tags
- Navigation defaults
  - project switch behavior
  - search default
  - Projects Home fallback

### 3. Define ownership of navigation defaults

For Release A:

- if editable, these are frontend-owned preferences
- if not editable, they are descriptive values rendered from fixed app behavior

Recommendation:

- render them descriptively in Release A
- do not add editable controls until behavior is settled

## Deferred To Release B

- editable metadata fields
- rename
- archive
- delete

Release B backend work would likely require:

- `PATCH /api/v1/projects/{slug}`
- explicit slug migration rules
- validation around filesystem path changes
- safety model for destructive actions

## Acceptance Criteria

- settings route exists and is reachable from project context
- displayed metadata matches project API responses
- navigation-default information matches actual app behavior
- future-state actions are clearly non-operational in Release A

## Tests

### Integration

- navigate to settings from a project shell
- verify metadata matches the loaded project
- verify settings page remains stable for projects with or without description
  and tags

## Risks

- users assuming fields are editable when they are not
- Release A silently growing into backend mutation work

Mitigation:

- make the page intentionally read-only in Release A
- keep future-state actions visually and functionally separated
