"""Real national MGS/PostGIS/GeoServer acceptance checks (no service mocks)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from participa_geo.db.session import session_scope, writer_engine
from participa_geo.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
ARCHIVES = ROOT / "data" / "raw" / "gis" / "national"


def test_imports_all_national_mgs_layers_in_4326_and_reuses_bridges():
    from pipelines.validation.geography_national import import_national_cartography

    settings = Settings()
    audit = import_national_cartography(ARCHIVES)
    with session_scope(writer_engine(settings)) as session:
        counts = session.execute(
            text("""
            SELECT
              (SELECT count(*) FROM geo_state),
              (SELECT count(*) FROM geo_municipality),
              (SELECT count(*) FROM geo_district_2023),
              (SELECT count(*) FROM geo_section),
              (SELECT count(*) FROM bridge_municipality_district),
              (SELECT count(DISTINCT (state_code,municipality_code))
               FROM bridge_municipality_district WHERE is_split),
              (SELECT count(*) FROM geo_district_2023 WHERE label LIKE 'Distrito % — %')
        """)
        ).one()
        crs = session.execute(
            text("""
            SELECT array_agg(DISTINCT ST_SRID(geom)) FROM (
              SELECT geom FROM geo_state UNION ALL
              SELECT geom FROM geo_municipality UNION ALL
              SELECT geom FROM geo_district_2023 UNION ALL
              SELECT geom FROM geo_section
            ) all_geometries
        """)
        ).scalar_one()
        valid = session.execute(
            text("""
            SELECT bool_and(NOT ST_IsEmpty(geom) AND ST_IsValid(geom))
            FROM (
              SELECT geom FROM geo_state UNION ALL
              SELECT geom FROM geo_municipality UNION ALL
              SELECT geom FROM geo_district_2023 UNION ALL
              SELECT geom FROM geo_section
            ) all_geometries
        """)
        ).scalar_one()
        source_srids = session.execute(
            text("SELECT array_agg(DISTINCT source_srid ORDER BY source_srid) FROM geo_state")
        ).scalar_one()

    assert audit.state_count == 32
    assert audit.municipality_count == 2477
    assert audit.district_count == 300
    assert counts[0:3] == (32, 2477, 300)
    assert counts[4:6] == (2581, 72)
    assert counts[6] == 300
    assert crs == [4326]
    assert valid
    assert source_srids == [32611, 32612, 32613, 32614, 32615, 32616]


def test_national_geoserver_services_are_public_read_only_and_bounded():
    from gis.geoserver.national import publish_national_layers, verify_national_layers

    settings = Settings()
    audit = publish_national_layers(settings)
    verification = verify_national_layers(settings)

    assert set(audit.layers) == {"states", "municipalities", "districts_2023"}
    assert verification["wms_capabilities_status"] == 200
    assert verification["national_getmap_png_bytes"] > 100
    assert verification["wfs_state_feature_count"] == 125
    assert verification["wfs_transaction_rejected"] is True
    assert verification["wfs_limit"] <= 1000


def test_gateway_forwards_state_scoped_wfs_and_national_wms(api_client):
    import json

    municipalities = api_client.get(
        "/api/v1/gis/wfs",
        params={
            "request": "GetFeature",
            "typeNames": "municipalities",
            "state_code": "14",
            "level": "municipality",
            "count": "1000",
        },
    )
    assert municipalities.status_code == 200
    assert len(json.loads(municipalities.content)["features"]) == 125

    districts = api_client.get(
        "/api/v1/gis/wfs",
        params={
            "request": "GetFeature",
            "typeNames": "districts_2023",
            "state_code": "14",
            "level": "federal_district",
            "count": "1000",
        },
    )
    assert districts.status_code == 200
    district_features = json.loads(districts.content)["features"]
    assert len(district_features) == 20
    assert any(
        feature["properties"]["label"].startswith("Distrito ")
        and " — " in feature["properties"]["label"]
        for feature in district_features
    )

    world_map = api_client.get(
        "/api/v1/gis/wms",
        params={
            "request": "GetMap",
            "layers": "states",
            "bbox": "-180,-85,180,85",
            "width": "512",
            "height": "512",
            "srs": "EPSG:4326",
            "format": "image/png",
        },
    )
    assert world_map.status_code == 200
    assert world_map.content.startswith(b"\x89PNG\r\n\x1a\n")

    district_map = api_client.get(
        "/api/v1/gis/wms",
        params={
            "request": "GetMap",
            "layers": "participa_geo_national:districts_2023",
            "bbox": "-118,-4,-86,34",
            "width": "512",
            "height": "512",
            "srs": "EPSG:4326",
            "format": "image/png",
        },
    )
    assert district_map.status_code == 200
    assert district_map.content.startswith(b"\x89PNG\r\n\x1a\n")
