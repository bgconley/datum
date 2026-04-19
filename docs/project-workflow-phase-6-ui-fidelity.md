# Phase 6 Engineering Spec: UI/UX Fidelity Implementation

## Objective

Bring the implemented project workflow screens into close visual alignment with
the approved Figma artifacts now that the workflow logic is stable.

This phase is not for redesigning the workflow. It is for tightening the
presentation so the built product matches the approved design intent at a much
higher level of precision.

## Inputs

Approved Figma file: `mO9DPr3qC7AbQTpJqHiTGu`

Relevant artifacts:

- `NX 11 — Projects Home`
- `NX 12 — Project Switcher`
- `NX 13 — Create Project Modal`
- `NX 14 — Projects Empty State`
- `NX 15 — Command Palette (Projects)`
- `NX 16 — Dashboard (New Project)`
- `NX 17 — Search Results (Project Scope)`
- `NX 18 — Project Settings`

Implementation baseline:

- project workflow logic has passed Phase 5 validation on the GPU node
- no structural workflow changes should be introduced during this phase unless a
  visual issue exposes a real usability defect

## Scope

### In scope

- typography scale and consistency
- spacing, padding, and layout rhythm
- card density and internal hierarchy
- shell consistency across header, sidebar, main content, and context rail
- button sizing and action emphasis
- truncation and text-wrapping behavior
- empty-state polish
- search-result card hierarchy
- settings-page composition

### Out of scope

- backend/API changes
- new workflow capabilities
- settings mutation work
- changes that alter the approved route and interaction model

## Screens To Tune

### Projects Home

Tune:

- summary-card composition
- pinned/recent panel balance
- project-index spacing and table rhythm
- workspace sidebar metrics treatment

### Project Switcher

Tune:

- overlay width and padding
- grouping between pinned, recent, and all projects
- active-project emphasis
- `Create Project` action placement and weight

### Create Project Modal

Tune:

- modal width and padding
- label/input spacing
- helper text density
- primary/secondary button hierarchy

### Projects Empty State

Tune:

- first-run message hierarchy
- CTA prominence
- alignment with the populated Projects Home shell

### Command Palette (Projects)

Tune:

- modal density
- grouping and separators
- action/result typography balance
- query-state presentation

### New Project Dashboard

Tune:

- onboarding hero composition
- first-action hierarchy
- relationship between onboarding content and system-health content

### Search Results (Project Scope)

Tune:

- top-of-page scope treatment
- synthesis spacing
- result-card metadata hierarchy
- balance between main results and the context rail

### Project Settings

Tune:

- panel proportions and column balance
- metadata hierarchy
- navigation-default presentation
- future-action separation and context-rail density

## Required Changes

### 1. Build a direct-comparison fidelity checklist

For each screen above, capture:

- structural deltas from Figma
- typography issues
- spacing/density issues
- truncation/wrapping issues
- visual-priority mismatches

This checklist must be based on direct Figma screenshots, not memory.

### 2. Normalize shared shell tokens first

Before making per-screen fixes, reconcile the shared shell:

- header height and chip treatment
- sidebar link density
- panel title treatment
- context-rail spacing
- button sizing tiers

The goal is to avoid isolated one-off fixes that make the shell inconsistent.

### 3. Tune each impacted screen against its approved Figma state

Implement screen-specific adjustments only after the shared shell is stable.

Do not invent alternate layouts that are not represented in the approved Figma
screens.

### 4. Preserve functional behavior while polishing

Every fidelity change must preserve:

- route behavior
- project switching behavior
- create-project flow
- scoped search behavior
- settings read-only contract

This phase should not invalidate the Phase 5 workflow pass.

## Execution Sequence

1. capture current implementation screenshots for all impacted screens
2. pull the matching Figma screenshots
3. document visual deltas in a working checklist
4. normalize shared shell styling
5. tune screen-specific layout, typography, and density
6. run local typecheck and build
7. run a local browser pass on all impacted screens
8. deploy the fidelity pass to the GPU node
9. rerun targeted Figma comparisons on the GPU-hosted app

## Acceptance Criteria

- each impacted screen has been compared directly against its Figma artifact
- the implemented layout matches the approved information hierarchy
- no major truncation, clipping, or density mismatches remain
- typography scale is consistent within and across screens
- shell components feel visually coherent across the full workflow
- no functional regressions are introduced while polishing

## Tests

### Local

- `npm run typecheck`
- `npm run build`
- Playwright screenshots for all impacted screens

### GPU-node

- deploy the fidelity pass to the GPU node
- capture screenshots for all impacted screens
- compare live GPU-hosted states against Figma

## Deliverables

- updated implementation aligned more closely to the approved Figma artifacts
- screenshot evidence for each tuned screen
- a short list of any residual intentional deviations, if any remain

## Risks

- introducing style-only regressions that alter routing or state behavior
- overfitting one screen while making the shared shell less coherent
- spending time on cosmetic churn without a stable comparison method

Mitigation:

- keep the workflow model locked during this phase
- compare against Figma screen by screen
- rerun targeted workflow checks after each meaningful fidelity cluster
