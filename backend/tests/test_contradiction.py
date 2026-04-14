"""Tests for contradiction detection."""

from datum.services.contradiction import detect_entity_property_conflicts, detect_version_conflicts


def test_detect_version_conflicts():
    conflicts = detect_version_conflicts(
        [
            {"entity": "PostgreSQL", "text": "PostgreSQL 14", "doc": "a.md", "version": "14"},
            {"entity": "PostgreSQL", "text": "PostgreSQL 16", "doc": "b.md", "version": "16"},
        ]
    )
    assert len(conflicts) == 1
    assert conflicts[0].insight_type == "contradiction"


def test_detect_entity_property_conflicts():
    conflicts = detect_entity_property_conflicts(
        [
            {"entity": "auth_service", "property": "port", "value": "8080", "doc": "a.md"},
            {"entity": "auth_service", "property": "port", "value": "3000", "doc": "b.md"},
        ]
    )
    assert len(conflicts) == 1
    assert conflicts[0].severity == "warning"
