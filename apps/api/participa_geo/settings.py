"""Application configuration, read from environment variables.

Secrets (the API database password and the GeoServer admin password) have no
default value and are validated as non-empty. Environment variable names are the
upper-cased field names (e.g. ``DB_API_PASSWORD``). The API only models the
``api`` database role it actually uses; the ``migrator``, ``writer`` and
``gis_reader`` roles belong to ``db-init.sh`` and are never used by the API.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    json_max_bytes: int = 32 * 1024  # 32768 (32 KiB)

    # Database — the API connects with the least-privilege ``api`` role.
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "participa_geo"
    db_api_user: str = "api"
    db_api_password: str = Field(..., min_length=1)

    # GeoServer — admin credentials are obligatory (internal network only).
    gis_admin_user: str = "admin"
    gis_admin_password: str = Field(..., min_length=1)
    gis_base_url: str = "http://geoserver:8080/geoserver"

    skip_demo_data: bool = True
