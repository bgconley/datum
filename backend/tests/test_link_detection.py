"""Tests for document link detection."""

from datum.services.link_detection import (
    detect_all_links,
    detect_markdown_links,
    detect_path_references,
)


def test_detect_markdown_links_relative_paths():
    result = detect_markdown_links("See [auth spec](docs/specs/auth.md) for details.")
    assert len(result) == 1
    assert result[0].target_path == "docs/specs/auth.md"
    assert result[0].anchor_text == "auth spec"


def test_detect_markdown_links_ignores_external_urls():
    result = detect_markdown_links("Visit [GitHub](https://github.com) and [Local](./docs/a.md)")
    assert [item.target_path for item in result] == ["docs/a.md"]


def test_detect_path_references_only_known_paths():
    result = detect_path_references(
        "The schema is defined in docs/schemas/init.sql and not in docs/missing.sql.",
        {"docs/schemas/init.sql"},
    )
    assert [item.target_path for item in result] == ["docs/schemas/init.sql"]


def test_detect_all_links_deduplicates_and_sorts():
    result = detect_all_links(
        "See [schema](docs/schema.sql) and docs/schema.sql in text.",
        {"docs/schema.sql"},
    )
    assert len(result) == 2
    assert result[0].start_char < result[1].start_char


def test_detect_all_links_empty_content():
    assert detect_all_links("", set()) == []
