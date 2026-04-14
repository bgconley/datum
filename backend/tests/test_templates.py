"""Tests for document templates."""

from datum.services.templates import get_template, list_templates, render_template


def test_list_templates_returns_expected_names():
    names = {item["name"] for item in list_templates()}
    assert {"adr", "prd", "requirements", "session-notes"} <= names


def test_get_template_returns_none_for_unknown():
    assert get_template("missing") is None


def test_render_template_includes_frontmatter_and_sections():
    rendered = render_template("adr", "Use PostgreSQL")
    assert rendered.startswith("---\n")
    assert "title: Use PostgreSQL" in rendered
    assert "## Decision" in rendered
