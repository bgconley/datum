"""Tests for content scanning and redaction."""

from datum.config import settings
from datum.services.boundaries import sanitize_agent_content
from datum.services.content_scanning import redact_content, scan_for_pii, scan_for_secrets


def test_scan_for_secrets_detects_patterns():
    matches = scan_for_secrets('PASSWORD="super_secret_123" and sk-proj-abc123def456ghi789')
    assert {item.match_type for item in matches} >= {"password", "api_key"}


def test_scan_for_pii_detects_email():
    matches = scan_for_pii("Contact john.doe@example.com for details.")
    assert any(item.match_type == "email" for item in matches)


def test_redact_content_replaces_matches():
    text = "Contact john.doe@example.com and use PASSWORD=topsecret123"
    redacted = redact_content(text, [*scan_for_pii(text), *scan_for_secrets(text)])
    assert "john.doe@example.com" not in redacted
    assert "[REDACTED" in redacted


def test_agent_content_always_redacts_secrets(tmp_path):
    settings.projects_root = tmp_path
    text = "Use sk-proj-abc123def456ghi789 immediately."
    redacted = sanitize_agent_content(text)
    assert "sk-proj-abc123def456ghi789" not in redacted
    assert "[REDACTED:api_key]" in redacted


def test_agent_content_redacts_pii_only_when_project_opted_in(tmp_path):
    settings.projects_root = tmp_path
    project_dir = tmp_path / "alpha"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text("name: Alpha\nslug: alpha\npii_redact_in_api: true\n")

    text = "Email john.doe@example.com about the release."
    redacted = sanitize_agent_content(text, project_slug="alpha")
    assert "john.doe@example.com" not in redacted
    assert "[REDACTED:email]" in redacted


def test_agent_content_keeps_pii_visible_by_default(tmp_path):
    settings.projects_root = tmp_path
    project_dir = tmp_path / "beta"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text("name: Beta\nslug: beta\n")

    text = "Email john.doe@example.com about the release."
    redacted = sanitize_agent_content(text, project_slug="beta")
    assert redacted == text
