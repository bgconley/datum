"""Tests for staleness detection helpers."""

from datetime import UTC, datetime, timedelta

from datum.services.staleness import detect_broken_links, detect_stale_documents


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
