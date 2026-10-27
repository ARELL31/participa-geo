"""Idempotent GeoServer publication of the four read-only layers.

Creates the ``participa_geo`` workspace, a PostGIS datastore (connecting as the
``gis_reader`` role), the four layers (``municipalities``, ``participation_history``,
``predictions``, ``scenario_results``) backed by the read-only DB views, uploads
the ``history``/``risk`` styles and hardens WFS to BASIC (no WFS-T).

Re-running ``publish_layers`` is idempotent: existing resources are updated, not
duplicated, and the admin password is never reset or logged.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from gis.geoserver.security import (
    WFS_SERVICE_LEVEL,
    _http,
    auth_header,
    get_wfs_settings,
    json_body,
    remove_foreign_workspaces,
    set_wfs_read_only,
    verify_transaction_rejected,
)
from participa_geo.settings import Settings

WORKSPACE = "participa_geo"
DATASTORE = "participa_geo"

#: Published layers → the DB view backing each, plus the assigned style.
#: ``municipalities`` is pure reference geometry (no analytic attributes), so it
#: uses the built-in ``polygon`` style; ``history``/``risk`` (with the gray
#: "insufficient" rule) apply to the analytic layers that carry those attributes.
LAYERS: dict[str, dict[str, str]] = {
    "municipalities": {"view": "municipalities", "style": "polygon"},
    "participation_history": {"view": "participation_history", "style": "history"},
    "predictions": {"view": "predictions", "style": "risk"},
    "scenario_results": {"view": "scenario_results", "style": "risk"},
}

_STYLE_FILES = {"history": "history.sld", "risk": "risk.sld"}

_READY_TIMEOUT_S = 180.0
_READY_POLL_S = 2.0


@dataclass(frozen=True)
class PublicationAudit:
    """Result of one idempotent GeoServer publication."""

    workspace: str
    datastore: str
    layers: list[str]
    wfs_service_level: str
    wfs_transaction_enabled: bool
    foreign_workspaces_removed: list[str]


def _styles_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "styles"


def _wait_until_ready(base_url: str, auth: dict[str, str]) -> None:
    deadline = time.monotonic() + _READY_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            status, _ = _http("GET", f"{base_url}/rest/about/version", auth=auth, timeout=5.0)
            if status == 200:
                return
        except ConnectionError:
            pass
        time.sleep(_READY_POLL_S)
    raise RuntimeError(
        f"GeoServer did not become ready within {_READY_TIMEOUT_S:.0f}s at {base_url}"
    )


def _ensure_workspace(base_url: str, auth: dict[str, str]) -> None:
    status, _ = _http("GET", f"{base_url}/rest/workspaces/{WORKSPACE}", auth=auth)
    if status == 200:
        return
    payload = json.dumps({"workspace": {"name": WORKSPACE}})
    status, body = _http(
        "POST", f"{base_url}/rest/workspaces", auth=auth, body=payload
    )
    if status not in (200, 201):
        raise RuntimeError(f"failed to create workspace ({status}): {body!r}")


def _datastore_payload(settings: Settings) -> str:
    params = [
        {"@key": "dbtype", "$": "postgis"},
        {"@key": "host", "$": settings.db_host},
        {"@key": "port", "$": str(settings.db_port)},
        {"@key": "database", "$": settings.db_name},
        {"@key": "schema", "$": "public"},
        {"@key": "user", "$": settings.db_gis_reader_user},
        {"@key": "passwd", "$": settings.db_gis_reader_password},
        {"@key": "validate connections", "$": "true"},
    ]
    return json.dumps(
        {
            "dataStore": {
                "name": DATASTORE,
                "type": "PostGIS",
                "enabled": True,
                "connectionParameters": {"entry": params},
            }
        }
    )


def _ensure_datastore(base_url: str, auth: dict[str, str], settings: Settings) -> None:
    url = f"{base_url}/rest/workspaces/{WORKSPACE}/datastores/{DATASTORE}"
    status, _ = _http("GET", url, auth=auth)
    if status == 200:
        return
    status, body = _http(
        "POST",
        f"{base_url}/rest/workspaces/{WORKSPACE}/datastores",
        auth=auth,
        body=_datastore_payload(settings),
    )
    if status not in (200, 201):
        raise RuntimeError(f"failed to create datastore ({status}): {body!r}")


def _ensure_feature_type(
    base_url: str, auth: dict[str, str], layer: str, native: str
) -> None:
    url = (
        f"{base_url}/rest/workspaces/{WORKSPACE}/datastores/{DATASTORE}/"
        f"featuretypes/{layer}"
    )
    status, _ = _http("GET", url, auth=auth)
    if status == 200:
        return
    payload = json.dumps(
        {
            "featureType": {
                "name": layer,
                "nativeName": native,
                "title": layer,
                "srs": "EPSG:4326",
                "enabled": True,
            }
        }
    )
    status, body = _http(
        "POST",
        f"{base_url}/rest/workspaces/{WORKSPACE}/datastores/{DATASTORE}/featuretypes",
        auth=auth,
        body=payload,
    )
    if status not in (200, 201):
        raise RuntimeError(f"failed to publish layer {layer} ({status}): {body!r}")


def _ensure_style(base_url: str, auth: dict[str, str], name: str) -> None:
    style_path = _styles_dir() / _STYLE_FILES[name]
    sld = style_path.read_text(encoding="utf-8")
    url = f"{base_url}/rest/workspaces/{WORKSPACE}/styles/{name}"
    status, _ = _http("GET", url, auth=auth)
    if status == 200:
        _http("PUT", url, auth=auth, body=sld, content_type="application/vnd.ogc.sld+xml")
    else:
        _http(
            "POST",
            f"{base_url}/rest/workspaces/{WORKSPACE}/styles?name={name}",
            auth=auth,
            body=sld,
            content_type="application/vnd.ogc.sld+xml",
        )


def _apply_style(
    base_url: str, auth: dict[str, str], layer: str, style: str
) -> None:
    payload = json.dumps({"layer": {"defaultStyle": {"name": style}}})
    _http(
        "PUT",
        f"{base_url}/rest/layers/{WORKSPACE}:{layer}",
        auth=auth,
        body=payload,
    )


def verify_layers(settings: Settings) -> dict:
    """Verify WMS/WFS with real GetCapabilities/GetMap/GetFeature.

    Checks that the ``municipalities`` layer is exposed, that an EPSG:3857 WMS
    GetMap returns a non-empty PNG, that an EPSG:4326 WFS GetFeature returns 125
    features, and that a WFS Transaction is rejected. Returns a small report.
    """
    from pyproj import Transformer

    base_url = settings.gis_base_url.rstrip("/")
    auth = auth_header(settings.gis_admin_user, settings.gis_admin_password)

    wms_caps_status, wms_caps = _http(
        "GET",
        f"{base_url}/wms?service=WMS&version=1.3.0&request=GetCapabilities",
        auth={},
    )
    wfs_caps_status, wfs_caps = _http(
        "GET",
        f"{base_url}/wfs?service=WFS&version=2.0.0&request=GetCapabilities",
        auth={},
    )

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x1, y1 = transformer.transform(-105.7, 18.9)
    x2, y2 = transformer.transform(-101.5, 22.75)
    bbox = f"{x1},{y1},{x2},{y2}"

    getmap_status, png = _http(
        "GET",
        f"{base_url}/wms?service=WMS&version=1.1.1&request=GetMap"
        f"&layers={WORKSPACE}:municipalities&styles="
        f"&bbox={bbox}&width=512&height=512&srs=EPSG:3857&format=image/png",
        auth={},
    )

    getfeature_status, geojson = _http(
        "GET",
        f"{base_url}/wfs?service=WFS&version=2.0.0&request=GetFeature"
        f"&typeNames={WORKSPACE}:municipalities&srsName=EPSG:4326"
        f"&outputFormat=application/json",
        auth={},
    )

    feature_count = 0
    if getfeature_status == 200 and geojson:
        try:
            feature_count = len(json_body(geojson).get("features", []))
        except (ValueError, AttributeError):
            feature_count = 0

    transaction_rejected = verify_transaction_rejected(base_url, auth)

    return {
        "wms_capabilities_status": wms_caps_status,
        "wfs_capabilities_status": wfs_caps_status,
        "getmap_status": getmap_status,
        "getmap_png_bytes": len(png),
        "getfeature_status": getfeature_status,
        "getfeature_count": feature_count,
        "wfs_transaction_rejected": transaction_rejected,
        "municipalities_layer_present": b"municipalities" in (wms_caps or b""),
    }


def publish_layers(settings: Settings) -> PublicationAudit:
    """Publish (or refresh) the four read-only layers and harden WFS."""
    if not settings.db_gis_reader_password:
        raise RuntimeError("DB_GIS_READER_PASSWORD is not set; cannot publish GIS layers")

    base_url = settings.gis_base_url.rstrip("/")
    auth = auth_header(settings.gis_admin_user, settings.gis_admin_password)

    _wait_until_ready(base_url, auth)
    _ensure_workspace(base_url, auth)
    _ensure_datastore(base_url, auth, settings)

    for layer, spec in LAYERS.items():
        _ensure_feature_type(base_url, auth, layer, spec["view"])

    for name in _STYLE_FILES:
        _ensure_style(base_url, auth, name)
    for layer, spec in LAYERS.items():
        _apply_style(base_url, auth, layer, spec["style"])

    set_wfs_read_only(base_url, auth)
    removed = remove_foreign_workspaces(base_url, auth, keep={WORKSPACE})

    wfs_settings = get_wfs_settings(base_url, auth)
    level = (wfs_settings or {}).get("serviceLevel", WFS_SERVICE_LEVEL)
    transaction_enabled = not verify_transaction_rejected(base_url, auth)

    return PublicationAudit(
        workspace=WORKSPACE,
        datastore=DATASTORE,
        layers=list(LAYERS),
        wfs_service_level=level,
        wfs_transaction_enabled=transaction_enabled,
        foreign_workspaces_removed=removed,
    )


__all__ = ["LAYERS", "PublicationAudit", "publish_layers", "verify_layers"]
