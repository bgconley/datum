# Phase 7 Engineering Spec: Final Integrated Validation And Sign-Off

## Objective

Run the complete project-workflow validation matrix one final time after the
Phase 6 fidelity pass and produce a release-quality sign-off result.

This phase validates the combined outcome:

- workflow behavior
- runtime correctness on the GPU node
- visual alignment with Figma
- absence of regressions introduced by the fidelity pass

## Preconditions

Phase 7 should not begin until:

- Phases 1 through 5 are complete
- Phase 6 fidelity work is implemented
- the fidelity changes are committed, pushed, pulled on the GPU node, and the
  GPU-hosted app is serving the new revision

## Validation Targets

### Workflow targets

- Projects Home
- Project Switcher
- Create Project
- Projects Empty State
- Command Palette (Projects)
- New Project Dashboard
- Search Results (Project Scope)
- Project Settings

### Runtime targets

- Datum frontend
- Datum API
- embedder
- reranker
- NER
- LLM

## Required Validation Matrix

### Projects Home

- load `/`
- verify project list renders correctly
- verify recent and pinned state render correctly
- verify workspace metrics render without stale state

### Create Project

- create from Projects Home
- create from Project Switcher
- create from Command Palette
- verify project appears immediately after creation
- verify landing on the onboarding dashboard state

### Project Switching

- switch from dashboard
- switch from inbox
- switch from sessions
- switch from search
- switch from settings
- switch from a document route and verify dashboard fallback

### Search

- verify global launch opens all-project context
- verify project-shell launch opens current-project context
- verify project-scoped query survives project switching
- verify query and retrieval mode are preserved while the scoped project changes

### Settings

- load settings for multiple projects
- verify metadata accuracy
- verify read-only messaging remains correct
- verify future-state actions remain non-operational

### Visual Comparison

For each approved Figma screen:

- capture the current GPU-hosted screenshot
- compare it to the canonical Figma screenshot
- verify information hierarchy, spacing, type scale, and affordance placement
- record any residual deviations

## Technical Validation

- no blocking browser console errors
- no warnings that indicate React state, routing, or hydration issues
- no route loops
- no stale shell selection after switching projects
- no create-project invalidation bugs
- no broken links or dead-end actions in the validated workflow

## Artifacts Required

- GPU-hosted screenshots for each validated screen
- the deployed revision under test
- confirmation of GPU runtime endpoints at test time
- final pass/fail status per scenario cluster

## Exit Criteria

- all workflow scenarios pass on the GPU-hosted app
- all major Figma comparisons are acceptable for production
- no unresolved project-workflow regressions remain
- any residual deviations are minor, intentional, and documented
- the implementation is ready to be treated as complete for Release A

## Failure Handling

If any validation fails:

1. classify the defect:
   - workflow bug
   - routing bug
   - styling/fidelity bug
   - runtime/environment issue
2. fix the issue in the smallest appropriate scope
3. redeploy to the GPU node
4. rerun the failed scenario plus adjacent regression checks
5. do not declare sign-off until the affected matrix is green again

## Deliverable

Produce a final validation summary that states:

- deployed revision
- runtime topology used
- scenarios passed
- artifacts captured
- any minor accepted deviations
- whether Release A project workflow work is complete
