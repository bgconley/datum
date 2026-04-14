import pytest
from pydantic import ValidationError

from datum.config import Settings


def test_lifecycle_settings_defaults(monkeypatch):
    monkeypatch.delenv("DATUM_LIFECYCLE_ENABLED", raising=False)
    monkeypatch.delenv("DATUM_LIFECYCLE_ENFORCEMENT_MODE", raising=False)
    monkeypatch.delenv("DATUM_PREFLIGHT_TTL_SECONDS", raising=False)
    monkeypatch.delenv("DATUM_SESSION_STALE_HOURS", raising=False)

    settings = Settings()

    assert settings.lifecycle_enabled is True
    assert settings.lifecycle_enforcement_mode == "advisory"
    assert settings.preflight_ttl_seconds == 300
    assert settings.session_stale_hours == 24


def test_settings_reject_invalid_lifecycle_enforcement_mode(monkeypatch):
    monkeypatch.setenv("DATUM_LIFECYCLE_ENFORCEMENT_MODE", "strict")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_invalid_preflight_ttl(monkeypatch):
    monkeypatch.setenv("DATUM_PREFLIGHT_TTL_SECONDS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_invalid_session_stale_hours(monkeypatch):
    monkeypatch.setenv("DATUM_SESSION_STALE_HOURS", "0")
    with pytest.raises(ValidationError):
        Settings()
