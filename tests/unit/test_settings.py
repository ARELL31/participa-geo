"""Unit tests for ``participa_geo.settings.Settings``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from participa_geo.settings import Settings


def test_missing_secret_rejected(monkeypatch):
    """Settings must fail when the DB password secret is absent."""
    monkeypatch.delenv("DB_API_PASSWORD", raising=False)
    monkeypatch.delenv("GIS_ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gis_admin_password="gis-secret")


def test_empty_secret_rejected():
    """An empty DB password is not a valid secret."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_api_password="", gis_admin_password="gis-secret")


def test_missing_gis_secret_rejected(monkeypatch):
    """GIS credentials are obligatory too."""
    monkeypatch.delenv("DB_API_PASSWORD", raising=False)
    monkeypatch.delenv("GIS_ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, db_api_password="api-secret")


def test_valid_settings_and_defaults(monkeypatch):
    monkeypatch.delenv("DB_API_PASSWORD", raising=False)
    monkeypatch.delenv("GIS_ADMIN_PASSWORD", raising=False)
    settings = Settings(
        _env_file=None,
        db_api_password="api-secret",
        gis_admin_password="gis-secret",
    )
    assert settings.db_host == "db"
    assert settings.db_port == 5432
    assert settings.db_name == "participa_geo"
    assert settings.db_api_user == "api"
    assert settings.gis_admin_user == "admin"
    assert settings.json_max_bytes == 32768
    assert settings.skip_demo_data is True
