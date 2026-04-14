"""Tests for insight orchestration helpers."""

from datum.services.insight_analysis import should_create_insight


def test_should_create_insight_for_new_title():
    assert should_create_insight("new", {}) is True


def test_should_not_create_duplicate_titles():
    for status in ("open", "acknowledged", "dismissed", "resolved", "false_positive"):
        assert should_create_insight("existing", {"existing": status}) is False
