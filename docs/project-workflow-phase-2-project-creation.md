# Phase 2 Engineering Spec: Project Creation And Post-Create Onboarding

## Objective

Make project creation a global, reusable workflow and land users in the correct
new-project state immediately after creation.

## Existing Anchors

- [frontend/src/components/CreateProjectDialog.tsx](../frontend/src/components/CreateProjectDialog.tsx)
- [backend/datum/api/projects.py](../backend/datum/api/projects.py)
- [backend/datum/schemas/project.py](../backend/datum/schemas/project.py)
- [frontend/src/components/ProjectDashboard.tsx](../frontend/src/components/ProjectDashboard.tsx)

## Release A Scope

- controlled create-project modal
- create from Projects Home
- create from Project Switcher
- create from Command Palette
- post-create navigation to the new dashboard
- new-project onboarding state on the dashboard

## Required Changes

### 1. Refactor create-project into a controlled modal

Current create flow is an inline expanding control. Refactor it into a reusable
modal component with:

- `open`
- `onOpenChange`
- `onCreated`
- optional `defaultName` or `source` metadata if useful

The modal should own:

- name input
- auto-generated slug
- manual slug editing
- description
- validation and error rendering

### 2. Add global launch points

Open the create modal from:

- Projects Home
- Project Switcher
- Command Palette

Do not duplicate form logic across surfaces.

### 3. Normalize post-create behavior

On successful create:

- invalidate `queryKeys.projects`
- prefetch `queryKeys.workspace(newSlug)`
- mark the new project as recent
- navigate to `/projects/:slug`
- render the approved new-project dashboard state

### 4. Define new-project dashboard conditions

The onboarding dashboard state should render when the project is effectively
empty. Suggested condition:

- no documents
- no generated files
- no pending review candidates
- no meaningful session history

The exact predicate should be centralized in one helper.

## Validation And Error Handling

### Required error states

- duplicate slug
- invalid slug
- network/API failure
- partially created project with DB sync warning but successful filesystem
  creation

### Success contract

Success is defined as:

- backend returns the created project
- project appears in the project list
- workspace query succeeds
- user lands on the new dashboard state

## Acceptance Criteria

- Create Project works from all intended entry points.
- The modal uses one code path everywhere.
- Successful creation immediately updates the visible project list.
- Successful creation lands on the new project dashboard.
- The new-project dashboard presents onboarding actions matching the approved
  design.

## Tests

### Unit

- slug generation
- slug manual override behavior
- empty-project predicate

### Integration

- create from Projects Home
- create from Project Switcher
- create from Command Palette
- handle duplicate slug cleanly
- verify query invalidation and visible list update
- verify post-create dashboard onboarding state

## Risks

- create success without immediate list/workspace refresh
- multiple modal implementations diverging
- dashboard empty-state logic becoming too fragile

Mitigation:

- centralize mutation success handling
- centralize empty-project state detection
