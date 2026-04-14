"""Predefined document templates for cabinet-first document creation."""

from __future__ import annotations

from datetime import date

TEMPLATES = {
    "adr": {
        "name": "adr",
        "title": "Architecture Decision Record",
        "description": "Structured ADR with context, decision, and consequences.",
        "doc_type": "decision",
        "default_folder": "docs/decisions",
        "filename_prefix": "adr-",
    },
    "prd": {
        "name": "prd",
        "title": "Product Requirements Document",
        "description": "Goals, scope, requirements, and success criteria.",
        "doc_type": "plan",
        "default_folder": "docs/plans",
        "filename_prefix": "prd-",
    },
    "requirements": {
        "name": "requirements",
        "title": "Requirements Specification",
        "description": "Requirement records with IDs, priorities, and acceptance criteria.",
        "doc_type": "requirements",
        "default_folder": "docs/requirements",
        "filename_prefix": "req-",
    },
    "session-notes": {
        "name": "session-notes",
        "title": "Session Notes",
        "description": "Summary, files modified, commands run, and next steps.",
        "doc_type": "session",
        "default_folder": "docs/sessions",
        "filename_prefix": "session-",
    },
}

_TEMPLATE_CONTENT = {
    "adr": """\
---
title: {title}
type: decision
status: proposed
created: {date}
tags: []
---

# {title}

## Status

Proposed

## Context

<!-- What problem or pressure led to this decision? -->

## Decision

<!-- What are we choosing? -->

## Consequences

<!-- What gets easier, harder, or riskier? -->
""",
    "prd": """\
---
title: {title}
type: plan
status: draft
created: {date}
tags: []
---

# {title}

## Overview

<!-- Brief feature or product summary -->

## Goals

- <!-- Goal 1 -->
- <!-- Goal 2 -->

## Non-Goals

- <!-- Explicitly out of scope -->

## Requirements

### Functional Requirements

- <!-- FR-1 -->

### Non-Functional Requirements

- <!-- NFR-1 -->

## Success Criteria

- <!-- Definition of done -->

## Open Questions

- <!-- Unknowns -->
""",
    "requirements": """\
---
title: {title}
type: requirements
status: draft
created: {date}
tags: []
---

# {title}

## Overview

<!-- Context for these requirements -->

## Requirements

### REQ-001: <!-- Requirement title -->

**Priority:** must
**Status:** active

<!-- Requirement description -->

**Acceptance Criteria:**
- <!-- Criterion 1 -->
""",
    "session-notes": """\
---
title: {title}
type: session
status: draft
created: {date}
tags: []
---

# {title}

## Summary

<!-- What happened in this session? -->

## Files Modified

- <!-- path/to/file -->

## Commands Run

```bash
# key commands
```

## Decisions Made

- <!-- notable decisions -->

## Next Steps

- [ ] <!-- follow-up -->
""",
}


def list_templates() -> list[dict[str, str]]:
    return list(TEMPLATES.values())


def get_template(name: str) -> dict[str, str] | None:
    return TEMPLATES.get(name)


def render_template(name: str, title: str) -> str:
    template = _TEMPLATE_CONTENT.get(name)
    if template is None:
        return ""
    return template.format(title=title, date=date.today().isoformat())
