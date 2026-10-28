"""Unit tests for the GIS gateway strict allowlist.

These never touch GeoServer or PostGIS: the gateway rejects forbidden
parameters (CQL, Transaction, REST/admin, arbitrary URLs, foreign layers,
unbounded bbox/size/count) before any upstream call, so a plain TestClient
(no database, no GeoServer) exercises the whole contract.
"""

from __future__ import annotations


def test_gis_gateway_bounds_national_wfs_by_state_and_limit():
    from participa_geo.api.gis_client import validate_wfs_request

    result = validate_wfs_request(
        {
            "request": "GetFeature",
            "typeNames": "municipalities",
            "state_code": "14",
            "level": "municipality",
            "count": "1000",
        }
    )
    assert result["count"] == "1000"
    assert result["cql_filter"] == "state_code = '14'"


def test_gis_gateway_wfs_accepts_bbox_without_state_and_caps_at_1000():
    from participa_geo.api.gis_client import validate_wfs_request

    result = validate_wfs_request(
        {
            "request": "GetFeature",
            "typeNames": "participa_geo_national:districts_2023",
            "bbox": "-117,14,-86,33,EPSG:4326",
        }
    )
    assert result["count"] == "1000"
    assert result["bbox"] == "-117,14,-86,33,EPSG:4326"


def test_gis_gateway_rejects_client_supplied_cql_and_scenario_filters():
    from participa_geo.api.errors import ProblemException
    from participa_geo.api.gis_client import validate_wfs_request

    for params in (
        {"request": "GetFeature", "typeNames": "municipalities", "CQL_FILTER": "INCLUDE"},
        {
            "request": "GetFeature",
            "typeNames": "predictions",
            "scenario_id": "00000000-0000-0000-0000-000000000001",
            "state_code": "14",
        },
    ):
        try:
            validate_wfs_request(params)
        except ProblemException:
            continue
        raise AssertionError("client-supplied filters must not reach GeoServer")


def test_gis_gateway_wfs_requires_state_or_bbox():
    from participa_geo.api.errors import ProblemException
    from participa_geo.api.gis_client import validate_wfs_request

    try:
        validate_wfs_request({"request": "GetFeature", "typeNames": "municipalities"})
    except ProblemException:
        return
    raise AssertionError("unbounded national WFS must be rejected")


def test_gis_gateway_rejects_cql_and_admin(api_client):
    response = api_client.get(
        "/api/v1/gis/wfs", params={"request": "GetFeature", "CQL_FILTER": "INCLUDE"}
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_gis_gateway_rejects_transaction(api_client):
    response = api_client.get(
        "/api/v1/gis/wfs",
        params={"request": "Transaction", "typeNames": "participa_geo:municipalities"},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_gis_gateway_rejects_arbitrary_url(api_client):
    response = api_client.get(
        "/api/v1/gis/wms",
        params={"request": "GetMap", "url": "http://attacker.example/evil"},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_gis_gateway_rejects_foreign_layer(api_client):
    response = api_client.get(
        "/api/v1/gis/wms",
        params={
            "request": "GetMap",
            "layers": "topp:states",
            "bbox": "-106.0,18.0,-101.0,23.0",
            "width": "256",
            "height": "256",
            "srs": "EPSG:3857",
            "format": "image/png",
        },
    )
    assert response.status_code == 422


def test_gis_gateway_rejects_unordered_bbox(api_client):
    response = api_client.get(
        "/api/v1/gis/wms",
        params={
            "request": "GetMap",
            "layers": "municipalities",
            "bbox": "-106.0,23.0,-101.0,18.0",  # miny > maxy
            "width": "256",
            "height": "256",
            "srs": "EPSG:3857",
            "format": "image/png",
        },
    )
    assert response.status_code == 422


def test_gis_gateway_rejects_non_finite_bbox(api_client):
    response = api_client.get(
        "/api/v1/gis/wms",
        params={
            "request": "GetMap",
            "layers": "municipalities",
            "bbox": "nan,18.0,-101.0,23.0",
            "width": "256",
            "height": "256",
            "srs": "EPSG:3857",
            "format": "image/png",
        },
    )
    assert response.status_code == 422


def test_gis_gateway_rejects_oversized_map(api_client):
    response = api_client.get(
        "/api/v1/gis/wms",
        params={
            "request": "GetMap",
            "layers": "municipalities",
            "bbox": "-106.0,18.0,-101.0,23.0",
            "width": "1201",
            "height": "256",
            "srs": "EPSG:3857",
            "format": "image/png",
        },
    )
    assert response.status_code == 422


def test_gis_gateway_rejects_count_over_limit(api_client):
    response = api_client.get(
        "/api/v1/gis/wfs",
        params={
            "request": "GetFeature",
            "typeNames": "municipalities",
            "count": "1001",
            "state_code": "14",
        },
    )
    assert response.status_code == 422


def test_gis_gateway_requires_entity_or_bbox_for_wfs(api_client):
    response = api_client.get(
        "/api/v1/gis/wfs",
        params={"request": "GetFeature", "typeNames": "municipalities", "count": "1000"},
    )
    assert response.status_code == 422


def test_gis_gateway_does_not_expose_geoserver_admin(api_client):
    response = api_client.get("/api/v1/gis/rest/workspaces")
    assert response.status_code == 404


def test_gis_gateway_rejects_unknown_request(api_client):
    response = api_client.get("/api/v1/gis/wms", params={"request": "RestAdmin"})
    assert response.status_code == 422


def _feature_info(**overrides):
    params = {
        "request": "GetFeatureInfo",
        "layers": "municipalities",
        "query_layers": "municipalities",
        "bbox": "-106.0,18.0,-101.0,23.0",
        "width": "256",
        "height": "256",
        "i": "10",
        "j": "10",
        "srs": "EPSG:3857",
        "info_format": "application/json",
    }
    params.update(overrides)
    return params


def test_gis_gateway_rejects_foreign_query_layers(api_client):
    response = api_client.get(
        "/api/v1/gis/wms",
        params=_feature_info(query_layers="topp:states"),
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_gis_gateway_requires_query_layers_inside_layers(api_client):
    response = api_client.get(
        "/api/v1/gis/wms",
        params=_feature_info(layers="municipalities", query_layers="predictions"),
    )
    assert response.status_code == 422


def test_gis_gateway_validates_feature_info_bbox_pixel_and_format(api_client):
    assert (
        api_client.get("/api/v1/gis/wms", params=_feature_info(bbox="nan,18,-101,23")).status_code
        == 422
    )
    assert (
        api_client.get(
            "/api/v1/gis/wms",
            params=_feature_info(bbox="-106,23,-101,18"),
        ).status_code
        == 422
    )
    assert api_client.get("/api/v1/gis/wms", params=_feature_info(i="256")).status_code == 422
    assert api_client.get("/api/v1/gis/wms", params=_feature_info(j="-1")).status_code == 422
    assert (
        api_client.get(
            "/api/v1/gis/wms",
            params=_feature_info(info_format="text/html"),
        ).status_code
        == 422
    )
    assert (
        api_client.get(
            "/api/v1/gis/wms",
            params=_feature_info(width="0"),
        ).status_code
        == 422
    )
