"""Integration tests for the reference-geometry import (INE MGS 15-DIC-2025).

These verify the real EPSG:32613 → EPSG:4326 reprojection, the fail-closed
checksum, and the idempotent audit. The geometry is never relabelled with
``set_crs``: the stored SRID is 4326 while ``source_srid`` records the declared
32613 source, and the coordinates fall inside Jalisco's lon/lat box.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


def test_import_records_source_and_target_srid(postgis_session):
    row = postgis_session.execute(
        text(
            """
            SELECT source_srid, ST_SRID(geometry), count(*)
            FROM territory_version
            WHERE reference_date = DATE '2025-12-15'
            GROUP BY source_srid, ST_SRID(geometry)
            """
        )
    ).all()
    assert {(r[0], r[1]): r[2] for r in row} == {(32613, 4326): 125}


def test_import_audit_fields(postgis_session, gis_archive):
    from pipelines.validation.geography import import_reference

    audit = import_reference(gis_archive, postgis_session)
    postgis_session.commit()

    assert audit.reference_count == 125
    assert audit.correspondence_count == 750
    assert audit.rejected_geometry_count == 0
    assert audit.source_crs == "EPSG:32613"
    assert audit.target_crs == "EPSG:4326"
    assert audit.reference_date == "2025-12-15"


def test_import_rejects_wrong_checksum(postgis_session, tmp_path):
    from pipelines.validation.geography import GeographyImportError, import_reference

    bogus = tmp_path / "bogus.zip"
    bogus.write_bytes(b"not a shapefile archive")
    with pytest.raises(GeographyImportError):
        import_reference(bogus, postgis_session)


def test_import_writes_auditable_geojson(postgis_session, gis_archive):
    from pipelines.validation.geography import import_reference

    audit = import_reference(gis_archive, postgis_session)
    postgis_session.commit()

    assert audit.output_geojson is not None and audit.output_geojson.exists()
    assert audit.output_sha256 is not None
