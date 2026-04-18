# Phase 5 Engineering Spec: GPU-Node Deployment And Validation

## Objective

Validate the implemented project workflow against the real GPU-node runtime and
the approved Figma artifacts before sign-off.

## Runtime Assumption

Validation happens on the GPU node where the intended inference services are
available. This phase is not complete until the deployed app is running against
the real service topology.

## Deployment Sequence

1. commit local changes intentionally
2. push to remote
3. pull on the GPU node
4. restart or reload the app against the expected runtime
5. verify service health and app reachability

## Expected Services

Confirm the target runtime is using the intended ports and roles before browser
validation:

- embedder
- reranker
- NER
- LLM
- Datum API
- Datum frontend

This phase should record the actual endpoints in use at test time.

## Required Functional Scenarios

### Projects Home

- load `/`
- render project list
- render empty state when no projects exist
- resume/open a project from home

### Project creation

- create a project from home
- create a project from switcher
- create a project from command palette
- verify project appears immediately after creation
- verify landing on new-project dashboard state

### Project switching

- switch from dashboard
- switch from inbox
- switch from sessions
- switch from search
- switch from a document route and verify dashboard fallback

### Search

- launch search from a project shell and confirm current-project default
- launch search globally and confirm all-project default
- switch search project without losing query

### Settings

- navigate to project settings
- verify metadata is accurate

## Visual Validation

Compare live app states against the approved Figma artifacts:

- Projects Home
- Project Switcher
- Create Project
- Empty State
- Command Palette
- New Project Dashboard
- Search Scope
- Project Settings

The standard is not pixel-perfect duplication of a mockup. The standard is:

- same information hierarchy
- same interaction model
- same visible workflow affordances
- no obvious typography, spacing, or truncation regressions

## Technical Validation

- no blocking browser console errors
- no route loops
- no stale selected-project shell state after switching
- correct query invalidation after project creation
- stable behavior on reload for local recents/pins

## Exit Criteria

- all required scenarios pass on the GPU node
- screenshots or recorded evidence exist for each major screen
- no unresolved shell/routing defects remain
- no mismatch exists between actual workflow behavior and the Release A spec

## Failure Handling

If validation fails:

- classify whether the issue is design drift, routing bug, state bug, or runtime
  environment problem
- fix the issue locally
- redeploy to the GPU node
- rerun only the affected validation matrix plus regression checks on the core
  project flows
