"""Publish national MGS map layers and verify the real WMS/WFS endpoint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from gis.geoserver.bootstrap import (
    _wait_until_ready,
)
from gis.geoserver.security import (
    _http,
    auth_header,
    remove_foreign_workspaces,
    set_wfs_read_only,
    verify_transaction_rejected,
)
from participa_geo.settings import Settings

WORKSPACE = "participa_geo_national"
DATASTORE = "participa_geo_national"
NATIONAL_LAYERS = {
    "states": {"native": "geo_state_national_view", "style": "national_states"},
    "municipalities": {
        "native": "geo_municipality_national_view",
        "style": "national_municipalities",
    },
    "districts_2023": {
        "native": "geo_district_2023_national_view",
        "style": "national_districts",
    },
}
_STYLE_FILES = {
    "national_states": "national_states.sld",
    "national_municipalities": "national_municipalities.sld",
    "national_districts": "national_districts.sld",
}


@dataclass(frozen=True)
class PublicationAudit:
    workspace: str
    datastore: str
    layers: list[str]
    wfs_service_level: str
    wfs_transaction_enabled: bool
    foreign_workspaces_removed: list[str]


def _style_path(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "styles" / _STYLE_FILES[name]


def _ensure_national_datastore(base: str, auth: dict[str, str], settings: Settings) -> None:
    store = DATASTORE
    store_url = f"{base}/rest/workspaces/{WORKSPACE}/datastores/{store}"
    status, _ = _http("GET", store_url, auth=auth)
    if status == 200:
        return
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
    body = json.dumps(
        {
            "dataStore": {
                "name": store,
                "type": "PostGIS",
                "enabled": True,
                "connectionParameters": {"entry": params},
            }
        }
    )
    status, response = _http(
        "POST", f"{base}/rest/workspaces/{WORKSPACE}/datastores", auth=auth, body=body
    )
    if status not in (200, 201):
        raise RuntimeError(f"failed to create national datastore ({status}): {response!r}")


def publish_national_layers(settings: Settings) -> PublicationAudit:
    """Publish geometries from the read-only PostGIS datastore, idempotently."""
    if not settings.db_gis_reader_password:
        raise RuntimeError("DB_GIS_READER_PASSWORD is not set; cannot publish GIS layers")
    base = settings.gis_base_url.rstrip("/")
    auth = auth_header(settings.gis_admin_user, settings.gis_admin_password)
    _wait_until_ready(base, auth)
    # Keep the MVP workspace and its existing municipalities feature type intact.
    status, _ = _http("GET", f"{base}/rest/workspaces/{WORKSPACE}", auth=auth)
    if status != 200:
        status, body = _http(
            "POST",
            f"{base}/rest/workspaces",
            auth=auth,
            body=json.dumps({"workspace": {"name": WORKSPACE}}),
        )
        if status not in (200, 201):
            raise RuntimeError(f"failed to create national workspace ({status}): {body!r}")
    _ensure_national_datastore(base, auth, settings)
    _http("POST", f"{base}/rest/reload", auth=auth)
    for layer, info in NATIONAL_LAYERS.items():
        feature_type_url = (
            f"{base}/rest/workspaces/{WORKSPACE}/datastores/{DATASTORE}/featuretypes/{layer}"
        )
        status, existing = _http("GET", f"{feature_type_url}.json", auth=auth)
        if status == 200:
            try:
                attributes = {
                    item["name"]
                    for item in json.loads(existing)
                    .get("featureType", {})
                    .get("attributes", {})
                    .get("attribute", [])
                }
            except (ValueError, TypeError, AttributeError):
                attributes = set()
            required_code = "district_code" if layer == "districts_2023" else "state_code"
            if required_code not in attributes:
                status, body = _http("DELETE", f"{feature_type_url}?recurse=true", auth=auth)
                if status not in (200, 404):
                    raise RuntimeError(f"failed to refresh stale feature type {layer}: {body!r}")
                status = 404
        payload = json.dumps(
            {
                "featureType": {
                    "name": layer,
                    "nativeName": info["native"],
                    "title": layer,
                    "srs": "EPSG:4326",
                    "enabled": True,
                }
            }
        )
        if status == 200:
            status, body = _http("PUT", feature_type_url, auth=auth, body=payload)
        else:
            legacy_url = f"{base}/rest/workspaces/{WORKSPACE}/datastores/{DATASTORE}/featuretypes"
            status, body = _http(
                "POST",
                legacy_url,
                auth=auth,
                body=payload,
            )
        if status not in (200, 201):
            raise RuntimeError(f"failed to publish national layer {layer} ({status}): {body!r}")
    for style in _STYLE_FILES:
        path = _style_path(style)
        body = path.read_text(encoding="utf-8")
        url = f"{base}/rest/workspaces/{WORKSPACE}/styles/{style}"
        status, _ = _http("GET", f"{url}.json", auth=auth)
        if status == 200:
            status, payload = _http(
                "PUT", url, auth=auth, body=body, content_type="application/vnd.ogc.sld+xml"
            )
        else:
            status, payload = _http(
                "POST",
                f"{base}/rest/workspaces/{WORKSPACE}/styles?name={style}",
                auth=auth,
                body=body,
                content_type="application/vnd.ogc.sld+xml",
            )
        if status not in (200, 201):
            raise RuntimeError(f"failed to publish style {style} ({status}): {payload!r}")
    for layer, info in NATIONAL_LAYERS.items():
        style = info["style"]
        body = json.dumps(
            {
                "layer": {
                    "defaultStyle": {"name": f"{WORKSPACE}:{style}"},
                    "styles": [],
                }
            }
        )
        _http("PUT", f"{base}/rest/layers/{WORKSPACE}:{layer}", auth=auth, body=body)
    set_wfs_read_only(base, auth)
    removed = remove_foreign_workspaces(base, auth, keep={WORKSPACE, "participa_geo"})
    return PublicationAudit(
        WORKSPACE, "participa_geo_national", list(NATIONAL_LAYERS), "BASIC", False, removed
    )


def verify_national_layers(settings: Settings) -> dict[str, object]:
    """Exercise public WMS/WFS requests against live GeoServer (without REST auth)."""
    base = settings.gis_base_url.rstrip("/")
    wms_status, capabilities = _http(
        "GET", f"{base}/wms?service=WMS&version=1.3.0&request=GetCapabilities", auth={}
    )
    wfs_status, _ = _http(
        "GET", f"{base}/wfs?service=WFS&version=2.0.0&request=GetCapabilities", auth={}
    )
    map_url = (
        f"{base}/wms?service=WMS&version=1.1.1&request=GetMap&"
        f"layers={WORKSPACE}:states&styles=&bbox=-180,-85,180,85&width=512&height=512&"
        "srs=EPSG:4326&format=image/png"
    )
    map_status, png = _http("GET", map_url, auth={})
    query = (
        f"service=WFS&version=2.0.0&request=GetFeature&typeNames={WORKSPACE}:municipalities&"
        "srsName=EPSG:4326&outputFormat=application/json&count=1000&"
        "CQL_FILTER=state_code%3D%2714%27"
    )
    feature_status, payload = _http("GET", f"{base}/wfs?{query}", auth={})
    feature_count = -1
    if feature_status == 200:
        feature_count = len(json.loads(payload.decode("utf-8")).get("features", []))
    transaction_rejected = verify_transaction_rejected(base, {})
    # Public API has no REST route; the GeoServer REST endpoint itself must not
    # disclose administrative resources without credentials.
    rest_status, _ = _http("GET", f"{base}/rest/workspaces", auth={})
    return {
        "wms_capabilities_status": wms_status,
        "wfs_capabilities_status": wfs_status,
        "capabilities_have_national_layers": all(
            name.encode() in (capabilities or b"") for name in NATIONAL_LAYERS
        ),
        "national_getmap_status": map_status,
        "national_getmap_png_bytes": len(png),
        "wfs_state_status": feature_status,
        "wfs_state_feature_count": feature_count,
        "wfs_limit": 1000,
        "wfs_transaction_rejected": transaction_rejected,
        "rest_anonymous_status": rest_status,
    }


__all__ = [
    "DATASTORE",
    "NATIONAL_LAYERS",
    "PublicationAudit",
    "WORKSPACE",
    "publish_national_layers",
    "verify_national_layers",
]
