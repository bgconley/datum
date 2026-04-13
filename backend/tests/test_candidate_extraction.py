
from datum.services.candidate_extraction import (
    extract_decisions_from_adr,
    extract_open_questions,
    extract_requirements,
)


class TestExtractDecisionsFromAdr:
    def test_extracts_structured_decision(self):
        text = """# ADR-0001: Use JWT Auth

## Status
Accepted

## Context
We need stateless auth for APIs.

## Decision
Use JWT with 15-minute expiry and refresh tokens.

## Consequences
Token revocation requires a denylist.
"""

        decisions = extract_decisions_from_adr(text)

        assert len(decisions) == 1
        candidate = decisions[0]
        assert candidate.title == "Use JWT Auth"
        assert candidate.status == "accepted"
        assert candidate.context == "We need stateless auth for APIs."
        assert "15-minute expiry" in (candidate.decision or "")
        assert "denylist" in (candidate.consequences or "")
        assert candidate.extraction_method == "structured_adr"
        assert candidate.confidence == 1.0

    def test_returns_empty_when_document_has_no_decision_section(self):
        text = """# Plan

## Context
Background only.
"""

        assert extract_decisions_from_adr(text) == []

    def test_handles_missing_optional_sections(self):
        text = """# ADR: Use ParadeDB

## Status
Proposed

## Decision
Use ParadeDB for BM25 and pgvector in one database.
"""

        decisions = extract_decisions_from_adr(text)

        assert len(decisions) == 1
        candidate = decisions[0]
        assert candidate.title == "Use ParadeDB"
        assert candidate.status == "proposed"
        assert candidate.context is None
        assert candidate.consequences is None


class TestExtractRequirements:
    def test_extracts_explicit_requirement_ids(self):
        text = """REQ-001: The API must reject stale writes.
US-002: The UI should show inbox counts."""

        requirements = extract_requirements(text)

        assert [item.requirement_id for item in requirements] == ["REQ-001", "US-002"]
        assert requirements[0].priority == "must"
        assert requirements[1].priority == "should"

    def test_extracts_shall_must_lines_without_ids(self):
        text = """The service must preserve canonical document paths in the database.
The dashboard should surface inbox counts.
"""

        requirements = extract_requirements(text)

        assert len(requirements) == 2
        assert requirements[0].requirement_id is None
        assert requirements[0].extraction_method == "regex_shall_must"
        assert requirements[1].priority == "should"

    def test_skips_requirement_like_lines_inside_code_blocks(self):
        text = """```yaml
service must not generate a requirement here
```

The worker must queue NER after extraction.
"""

        requirements = extract_requirements(text)

        assert len(requirements) == 1
        assert "worker must queue" in requirements[0].title

    def test_skips_question_lines_that_happen_to_contain_should(self):
        text = """Open question: Should cache invalidation track version_scope?
QUESTION: Should the inbox sort by severity?
"""

        assert extract_requirements(text) == []


class TestExtractOpenQuestions:
    def test_extracts_question_lines_and_todo_markers(self):
        text = """Should we keep a restore button in the history panel?
TODO: confirm GPU-node GLiNER startup flow
"""

        questions = extract_open_questions(text)

        assert len(questions) == 2
        assert questions[0].extraction_method == "regex_question_mark"
        assert questions[1].extraction_method == "regex_todo_marker"

    def test_skips_headings_and_code_blocks(self):
        text = """## What next?

```python
print("Should this become a candidate?")
```

What is the rollback story for this migration?
"""

        questions = extract_open_questions(text)

        assert len(questions) == 1
        assert questions[0].question == "What is the rollback story for this migration?"

    def test_normalizes_open_question_prefixes(self):
        text = """Open question: Should cache invalidation track version_scope?
QUESTION: How should dashboards handle stale entities?
"""

        questions = extract_open_questions(text)

        assert [item.question for item in questions] == [
            "Should cache invalidation track version_scope?",
            "How should dashboards handle stale entities?",
        ]
        assert questions[0].extraction_method == "regex_question_mark"
