"""Unit tests for the GIS gateway strict allowlist.

These never touch GeoServer or PostGIS: the gateway rejects forbidden
parameters (CQL, Transaction, REST/admin, arbitrary URLs, foreign layers,
unbounded bbox/size/count) before any upstream call, so a plain TestClient
(no database, no GeoServer) exercises the whole contract.
"""

from __future__ import annotations


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
        params={"request": "GetFeature", "typeNames": "municipalities", "count": "126"},
    )
    assert response.status_code == 422


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
        params=_feature_info(
            layers="municipalities", query_layers="predictions"
        ),
    )
    assert response.status_code == 422


def test_gis_gateway_validates_feature_info_bbox_pixel_and_format(api_client):
    assert (
        api_client.get(
            "/api/v1/gis/wms", params=_feature_info(bbox="nan,18,-101,23")
        ).status_code
        == 422
    )
    assert (
        api_client.get(
            "/api/v1/gis/wms",
            params=_feature_info(bbox="-106,23,-101,18"),
        ).status_code
        == 422
    )
    assert (
        api_client.get(
            "/api/v1/gis/wms", params=_feature_info(i="256")
        ).status_code
        == 422
    )
    assert (
        api_client.get(
            "/api/v1/gis/wms", params=_feature_info(j="-1")
        ).status_code
        == 422
    )
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
