"""Declarative security checks over ``compose.yaml`` and ``.env.example``.

These tests run inside the api container (``docker compose run --rm --no-deps
api pytest tests/integration/test_compose_security.py``) and inspect the compose
file mounted at the repository root. They do not start the database or
GeoServer; they verify the declarative configuration only.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "compose.yaml"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

COMPOSE_TEXT = COMPOSE_PATH.read_text()
COMPOSE = yaml.safe_load(COMPOSE_TEXT)

SERVICES = COMPOSE["services"]


def _env(service: str) -> dict[str, str]:
    """Flatten the ``environment`` of a service to a plain dict (list or map)."""
    raw = SERVICES[service]["environment"]
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    result: dict[str, str] = {}
    for item in raw:
        key, _, value = item.partition("=")
        result[key] = value
    return result


def test_db_and_geoserver_publish_no_host_ports():
    for name in ("db", "geoserver"):
        assert "ports" not in SERVICES[name], f"{name} must not publish host ports"


def test_only_web_publishes_loopback_port():
    assert "ports" not in SERVICES["api"], "api must be reachable only through web"
    assert SERVICES["web"]["ports"] == ["127.0.0.1:${WEB_PORT:-8080}:80"]


def test_images_are_pinned_by_digest():
    for name in ("db", "geoserver"):
        image = SERVICES[name]["image"]
        assert "@sha256:" in image, f"{name} image must be pinned by digest"


def test_web_dockerfile_uses_pinned_node_and_nginx():
    dockerfile = (REPO_ROOT / "infrastructure/docker/web.Dockerfile").read_text()
    assert "node:24-bookworm-slim@sha256:" in dockerfile
    assert "nginx:1.29-bookworm@sha256:" in dockerfile
    assert ":latest" not in dockerfile


def test_web_proxies_the_api_and_never_geoserver():
    nginx = (REPO_ROOT / "infrastructure/docker/nginx.conf").read_text().lower()
    assert "proxy_pass http://api:8000;" in nginx
    assert "proxy_pass http://geoserver" not in nginx
    assert "proxy_pass http://participa_geo" not in nginx
    # Administrative GIS paths are explicitly blocked instead of falling back
    # to index.html; the GIS admin only exists on the internal network.
    assert "location /geoserver/" in nginx
    assert "return 404;" in nginx


def test_password_secrets_have_no_default():
    db_env = _env("db")
    geoserver_env = _env("geoserver")
    api_env = _env("api")

    # Required (no default fallback) interpolation for every secret.
    assert db_env["POSTGRES_PASSWORD"].startswith("${POSTGRES_PASSWORD:?")
    assert db_env["DB_API_PASSWORD"].startswith("${DB_API_PASSWORD:?")
    assert db_env["DB_MIGRATOR_PASSWORD"].startswith("${DB_MIGRATOR_PASSWORD:?")
    assert db_env["DB_WRITER_PASSWORD"].startswith("${DB_WRITER_PASSWORD:?")
    assert db_env["DB_GIS_READER_PASSWORD"].startswith("${DB_GIS_READER_PASSWORD:?")
    assert geoserver_env["GEOSERVER_ADMIN_PASSWORD"].startswith("${GIS_ADMIN_PASSWORD:?")
    assert api_env["DB_API_PASSWORD"].startswith("${DB_API_PASSWORD:?")
    assert api_env["GIS_ADMIN_PASSWORD"].startswith("${GIS_ADMIN_PASSWORD:?")

    # No literal default credentials anywhere in the compose file.
    lowered = COMPOSE_TEXT.lower()
    assert "password: postgres" not in lowered
    assert "password: geoserver" not in lowered


def test_db_and_geoserver_reachable_only_from_backend_network():
    # Isolation is via "no published ports": db and geoserver attach only to the
    # internal bridge network and expose nothing on the host.
    assert "internal" in COMPOSE["networks"]
    assert COMPOSE["networks"]["internal"].get("driver") == "bridge"
    for name in ("db", "geoserver"):
        assert SERVICES[name]["networks"] == ["internal"]
    for name in ("api", "web"):
        assert SERVICES[name]["networks"] == ["internal"]


def test_env_example_has_placeholders_not_secrets():
    text = ENV_EXAMPLE_PATH.read_text()
    assert "change-me-" in text
    # Placeholders, not real credential defaults shipped as usable values.
    for forbidden in ("POSTGRES_PASSWORD=postgres", "GIS_ADMIN_PASSWORD=geoserver"):
        assert forbidden not in text


def test_web_can_start_before_data_model_and_gis_are_ready():
    """Item 12: staged startup must not be blocked by API readiness."""
    depends = SERVICES["web"]["depends_on"]
    assert depends["api"]["condition"] == "service_started"


def test_api_mounts_national_source_export_scripts_read_only():
    volumes = SERVICES["api"]["volumes"]
    assert "./scripts:/workspace/scripts:ro" in volumes


def test_services_rotate_logs_and_web_is_healthchecked():
    for name in ("api", "web", "db", "geoserver"):
        logging = SERVICES[name]["logging"]
        assert logging["driver"] == "json-file"
        assert logging["options"]["max-size"] == "10m"
        assert logging["options"]["max-file"] == "3"
    web_healthcheck = SERVICES["web"]["healthcheck"]["test"]
    assert web_healthcheck[:2] == ["CMD", "curl"]
    assert "http://127.0.0.1/healthz" in web_healthcheck
