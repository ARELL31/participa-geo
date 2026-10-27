"""Reference-geometry import and validation (INE MGS 15-DIC-2025 → PostGIS).

The official INE municipal shapefile for Jalisco is a ZIP whose ``MUNICIPIO.shp``
carries 125 Polygon/MultiPolygon geometries in EPSG:32613. This module:

1. verifies the ZIP SHA-256 (fail closed),
2. reads the shapefile with GeoPandas,
3. rejects empty/invalid geometries **before** any repair,
4. reprojects with ``.to_crs(4326)`` (never ``.set_crs`` over UTM),
5. bounds-checks longitude/latitude against Jalisco (-107..-100, 18..23),
6. upserts 125 reference territories (EPSG:4326) and the 750 origin↔reference
   correspondences with ``identity_status=verified_catalogue`` and
   ``footprint_status=not_verified``,
7. writes an auditable GeoJSON + SHA-256 sidecar.

The import is idempotent (deterministic ``uuid5`` ids and ``ON CONFLICT``).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import geopandas as gpd
from shapely import is_empty, is_valid, to_wkb
from sqlalchemy import text
from sqlalchemy.orm import Session

from participa_geo.ingestion.schema import (
    ELECTION_YEARS,
    REFERENCE_DATE,
    observation_id,
    territory_id,
)

#: Verified SHA-256 of the INE MGS 15-DIC-2025 Jalisco ZIP (source date 2025-12-15).
REFERENCE_ARCHIVE_SHA256 = "7b252438a67d904a42a7b912ff29bef74a2ed79675a609143e74a592ef872a50"

SOURCE_CRS = "EPSG:32613"
TARGET_CRS = "EPSG:4326"

#: Jalisco bounding box in lon/lat (inclusive).
LON_MIN, LON_MAX = -107.0, -100.0
LAT_MIN, LAT_MAX = 18.0, 23.0

_MEMBER = "14/MUNICIPIO.shp"


class GeographyImportError(RuntimeError):
    """Raised when the reference archive or geometry fails validation."""


@dataclass(frozen=True)
class GeographyAudit:
    """Result of one reference-geometry import."""

    reference_count: int
    correspondence_count: int
    rejected_geometry_count: int
    source_crs: str
    target_crs: str
    reference_date: str
    archive_sha256: str
    output_geojson: Path | None
    output_sha256: str | None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _read_reference_frame(archive: Path) -> gpd.GeoDataFrame:
    if not archive.exists():
        raise GeographyImportError(f"reference archive not found: {archive}")
    actual = _sha256_file(archive)
    if actual != REFERENCE_ARCHIVE_SHA256:
        raise GeographyImportError(
            f"{archive.name}: SHA-256 mismatch: expected {REFERENCE_ARCHIVE_SHA256}, "
            f"got {actual}"
        )

    vsizip = f"/vsizip/{archive.resolve()}/{_MEMBER}"
    try:
        frame = gpd.read_file(vsizip)
    except Exception as exc:  # noqa: BLE001 - report the archive/member, not the trace
        raise GeographyImportError(
            f"could not read {_MEMBER} from {archive.name}: {exc}"
        ) from exc

    if str(frame.crs) != SOURCE_CRS:
        raise GeographyImportError(
            f"{archive.name}: declared CRS is {frame.crs}, expected {SOURCE_CRS}"
        )
    return frame


def import_reference(archive: Path, session: Session) -> GeographyAudit:
    """Import the verified INE 2025 reference geometry and correspondences.

    Idempotent: deterministic ids and ``ON CONFLICT`` mean re-running neither
    duplicates rows nor invents historical geometry. Historical origin identities
    keep ``geometry IS NULL``.
    """
    frame = _read_reference_frame(archive)

    if len(frame) != 125:
        raise GeographyImportError(
            f"expected 125 municipality geometries, got {len(frame)}"
        )
    if frame["geometry"].isna().any():
        raise GeographyImportError("archive contains null geometries")

    geometry = frame["geometry"]
    invalid_mask = ~geometry.apply(lambda g: is_valid(g) and not is_empty(g))
    rejected = int(invalid_mask.sum())
    if rejected:
        raise GeographyImportError(
            f"{rejected} invalid/empty geometries; rejecting the import "
            "before any repair"
        )

    # Real reprojection (never .set_crs over UTM).
    frame = frame.to_crs(TARGET_CRS)
    minx, miny, maxx, maxy = frame.total_bounds
    if not (LON_MIN <= minx and maxx <= LON_MAX and LAT_MIN <= miny and maxy <= LAT_MAX):
        raise GeographyImportError(
            f"geometry outside Jalisco bounds: lon [{minx}, {maxx}], lat [{miny}, {maxy}]"
        )

    # Catalogue of origin identities already loaded by ``db load``.
    known_codes = {
        row[0]
        for row in session.execute(
            text(
                "SELECT DISTINCT municipality_code FROM territory_version "
                "WHERE origin_year IS NOT NULL"
            )
        )
    }

    reference_date = date.fromisoformat(REFERENCE_DATE)
    reference_count = 0
    correspondence_count = 0

    for _, row in frame.iterrows():
        state_code = str(int(row["entidad"])).zfill(2)
        code = str(int(row["municipio"])).zfill(3)
        name = str(row["nombre"]).strip()
        ref_id = territory_id(state_code, code)

        session.execute(
            text(
                """
                INSERT INTO territory_version
                    (id, system, state_code, municipality_code, name, reference_date,
                     origin_year, geometry, source_srid, provenance)
                VALUES
                    (:id, 'ine', :state, :code, :name, :ref_date, NULL,
                     ST_SetSRID(ST_GeomFromWKB(:wkb), 4326), :srid, :prov)
                ON CONFLICT (id) DO UPDATE SET
                    geometry = EXCLUDED.geometry,
                    name = EXCLUDED.name,
                    source_srid = EXCLUDED.source_srid
                """
            ),
            {
                "id": ref_id,
                "state": state_code,
                "code": code,
                "name": name,
                "ref_date": reference_date,
                "wkb": to_wkb(row["geometry"]),
                "srid": 32613,
                "prov": "ine-mgs-2025-12-15",
            },
        )
        reference_count += 1

        # Identity status: catalogue code/name match is verified (research),
        # but historical footprint equality is NOT verified.
        identity = "verified_catalogue" if code in known_codes else "ambiguous"
        footprint = "not_verified"
        for year in ELECTION_YEARS:
            origin_id = observation_id(state_code, code, year)
            corr_id = uuid5(
                NAMESPACE_URL, f"correspondence:{origin_id}:{ref_id}"
            )
            session.execute(
                text(
                    """
                    INSERT INTO territory_correspondence
                        (id, origin_territory_id, reference_territory_id,
                         relation_type, evidence, identity_status, footprint_status)
                    VALUES
                        (:id, :origin, :reference, 'catalogue_match', :evidence,
                         :identity, :footprint)
                    ON CONFLICT (origin_territory_id, reference_territory_id)
                    DO UPDATE SET
                        identity_status = EXCLUDED.identity_status,
                        footprint_status = EXCLUDED.footprint_status
                    """
                ),
                {
                    "id": corr_id,
                    "origin": origin_id,
                    "reference": ref_id,
                    "evidence": json.dumps(
                        {"source": "ine-mgs-2025-12-15", "origin_year": year}
                    ),
                    "identity": identity,
                    "footprint": footprint,
                },
            )
            correspondence_count += 1

    # Auditable processed geography (git-ignored).
    output_dir = Path.cwd() / "data" / "processed" / "gis"
    geojson_path = output_dir / f"reference-{REFERENCE_DATE}.geojson"
    geojson_bytes = frame.to_crs(TARGET_CRS).to_json().encode("utf-8")
    _atomic_write_bytes(geojson_path, geojson_bytes)
    checksum = hashlib.sha256(geojson_bytes).hexdigest()
    _atomic_write_bytes(
        output_dir / f"reference-{REFERENCE_DATE}.geojson.sha256",
        (checksum + "\n").encode("utf-8"),
    )

    return GeographyAudit(
        reference_count=reference_count,
        correspondence_count=correspondence_count,
        rejected_geometry_count=rejected,
        source_crs=SOURCE_CRS,
        target_crs=TARGET_CRS,
        reference_date=REFERENCE_DATE,
        archive_sha256=REFERENCE_ARCHIVE_SHA256,
        output_geojson=geojson_path,
        output_sha256=checksum,
    )


__all__ = ["GeographyAudit", "GeographyImportError", "import_reference"]
