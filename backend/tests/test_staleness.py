"""Tests for staleness detection helpers."""

from datetime import UTC, datetime, timedelta

from datum.services.staleness import (
    detect_aged_open_questions,
    detect_broken_links,
    detect_stale_documents,
)


def test_detect_stale_documents():
    now = datetime.now(UTC)
    candidates = detect_stale_documents(
        [
            {"path": "docs/old.md", "updated_at": now - timedelta(days=90)},
            {"path": "docs/new.md", "updated_at": now - timedelta(days=5)},
        ],
        max_age_days=60,
    )
    assert len(candidates) == 1
    assert "docs/old.md" in candidates[0].title


def test_detect_broken_links():
    candidates = detect_broken_links(
        [{"source": "docs/a.md", "target_path": "docs/missing.md", "anchor": "missing"}],
        {"docs/a.md", "docs/b.md"},
    )
    assert len(candidates) == 1
    assert "docs/missing.md" in candidates[0].title


def test_detect_aged_open_questions():
    now = datetime.now(UTC)
    candidates = detect_aged_open_questions(
        [
            {
                "question": "What is the rollback plan?",
                "created_at": now - timedelta(days=45),
                "document_path": "docs/ops.md",
                "source_version": 3,
                "canonical_record_path": ".piq/records/open-questions/oq_1.yaml",
            },
            {
                "question": "What color should the button be?",
                "created_at": now - timedelta(days=5),
                "document_path": "docs/ui.md",
                "source_version": 1,
                "canonical_record_path": ".piq/records/open-questions/oq_2.yaml",
            },
        ]
    )

    assert len(candidates) == 1
    assert candidates[0].insight_type == "open_question_aging"
    assert candidates[0].evidence["document_path"] == "docs/ops.md"
    assert candidates[0].evidence["source_version"] == 3
