"""Import and audit INE MGS national geometries in PostGIS (EPSG:4326)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import geopandas as gpd
from shapely import is_empty, is_valid, to_wkb
from sqlalchemy import text

from participa_geo.db.session import session_scope, writer_engine
from participa_geo.ingestion.continuity import read_district_labels
from participa_geo.settings import Settings

SOURCE_CUT = date(2025, 12, 15)
TARGET_SRID = 4326
_LAYERS = {
    "ENTIDAD": ("geo_state", ("entidad", "nombre")),
    "MUNICIPIO": ("geo_municipality", ("entidad", "municipio", "nombre")),
    "DISTRITO_FEDERAL": ("geo_district_2023", ("entidad", "distrito_f")),
    "SECCION": ("geo_section", ("entidad", "municipio", "seccion", "distrito_f")),
}
_STATE_UTM_EPSG = {
    **{state: 32611 for state in ("02",)},
    **{state: 32612 for state in ("03", "26")},
    **{state: 32613 for state in ("01", "06", "08", "10", "14", "18", "25", "32")},
    **{
        state: 32614
        for state in (
            "05",
            "09",
            "11",
            "12",
            "13",
            "15",
            "16",
            "17",
            "19",
            "20",
            "21",
            "22",
            "24",
            "28",
            "29",
            "30",
        )
    },
    **{state: 32615 for state in ("04", "07", "27")},
    **{state: 32616 for state in ("23", "31")},
}


class NationalGeographyError(RuntimeError):
    """National source or geometry does not meet the import contract."""


@dataclass(frozen=True)
class GeographyAudit:
    state_count: int
    municipality_count: int
    district_count: int
    section_count: int
    archive_count: int
    source_cut: str
    target_crs: str
    archive_sha256: dict[str, str]
    municipality_district_pair_count: int
    split_municipality_count: int


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_layer(archive: Path, state: str, layer: str) -> gpd.GeoDataFrame:
    member = f"/vsizip/{archive.resolve()}/{state}/{layer}.shp"
    try:
        frame = gpd.read_file(member)
    except Exception as exc:  # noqa: BLE001 - retain archive/member context
        raise NationalGeographyError(f"cannot read {member}: {exc}") from exc
    expected = _STATE_UTM_EPSG[state]
    actual = frame.crs.to_epsg() if frame.crs else None
    if actual != expected:
        raise NationalGeographyError(
            f"{state}/{layer}: CRS EPSG:{actual} does not match expected EPSG:{expected}"
        )
    if frame.empty or frame.geometry.isna().any():
        raise NationalGeographyError(f"{state}/{layer}: empty layer or null geometry")
    invalid = frame.geometry.apply(lambda geom: is_empty(geom) or not is_valid(geom))
    if invalid.any():
        raise NationalGeographyError(
            f"{state}/{layer}: rejected {int(invalid.sum())} empty/invalid geometries"
        )
    return frame.to_crs(epsg=TARGET_SRID)


def _load_labels() -> dict[tuple[str, str], str]:
    path = Path("data/raw/continuity/district-headquarters.txt")
    labels = read_district_labels(path)
    if len(labels) != 300:
        raise NationalGeographyError(
            "official district-headquarters catalogue must contain 300 unique labels, "
            f"found {len(labels)}"
        )
    return labels


def import_national_cartography(archive_dir: Path) -> GeographyAudit:
    """Replace all four MGS layers atomically after validating all 32 archives."""
    archive_dir = Path(archive_dir)
    labels = _load_labels()
    archives = {f"{number:02d}": archive_dir / f"{number:02d}.zip" for number in range(1, 33)}
    missing = [str(path) for path in archives.values() if not path.is_file()]
    if missing:
        raise NationalGeographyError(f"missing MGS archives: {missing}")
    hashes = {state: _hash(path) for state, path in archives.items()}

    settings = Settings()
    counts = {table: 0 for table, _ in _LAYERS.values()}
    with session_scope(writer_engine(settings)) as session:
        # Delete only after every archive has been found and hashed. The enclosing
        # session transaction rolls back if any subsequent state/layer fails.
        for table in ("geo_section", "geo_district_2023", "geo_municipality", "geo_state"):
            session.execute(text(f"DELETE FROM {table}"))
        for state, archive in archives.items():
            for layer, (table, fields) in _LAYERS.items():
                frame = _read_layer(archive, state, layer)
                source_srid = _STATE_UTM_EPSG[state]
                rows = []
                for _, feature in frame.iterrows():
                    attrs = [
                        (
                            str(int(feature[field])).zfill(2)
                            if field in {"entidad", "distrito_f"}
                            else str(int(feature[field])).zfill(3)
                            if field == "municipio"
                            else str(int(feature[field]))
                        )
                        for field in fields
                        if field != "nombre"
                    ]
                    if layer == "ENTIDAD":
                        code, name = attrs[0], str(feature["nombre"]).strip()
                        row = {"state": code, "name": name}
                    elif layer == "MUNICIPIO":
                        code, municipality, name = (
                            attrs[0],
                            attrs[1],
                            str(feature["nombre"]).strip(),
                        )
                        row = {"state": code, "municipality": municipality, "name": name}
                    elif layer == "DISTRITO_FEDERAL":
                        code, district = attrs
                        label = labels.get((code, district))
                        if not label:
                            raise NationalGeographyError(
                                f"no official label for district {code}/{district}"
                            )
                        row = {"state": code, "district": district, "label": label}
                    else:
                        code, municipality, section, district = attrs
                        row = {
                            "state": code,
                            "municipality": municipality,
                            "section": section,
                            "district": district,
                        }
                    row.update(
                        {
                            "geom": to_wkb(feature.geometry),
                            "source_cut": SOURCE_CUT,
                            "source_srid": source_srid,
                            "archive_sha256": hashes[state],
                            "provenance": (
                                f"INE MGS 15-DIC-2025; archive={state}.zip; "
                                f"source EPSG:{source_srid}; transformed with GeoPandas "
                                "to EPSG:4326"
                            ),
                        }
                    )
                    rows.append(row)
                column_sql = {
                    "geo_state": (
                        "state_code,name,geom,source_cut,source_srid,archive_sha256,provenance"
                    ),
                    "geo_municipality": (
                        "state_code,municipality_code,name,geom,source_cut,source_srid,"
                        "archive_sha256,provenance"
                    ),
                    "geo_district_2023": (
                        "state_code,district_code,label,geom,source_cut,source_srid,"
                        "archive_sha256,provenance"
                    ),
                    "geo_section": (
                        "state_code,municipality_code,section_code,district_code,geom,"
                        "source_cut,source_srid,archive_sha256,provenance"
                    ),
                }[table]
                params = {
                    "geo_state": "state,name",
                    "geo_municipality": "state,municipality,name",
                    "geo_district_2023": "state,district,label",
                    "geo_section": "state,municipality,section,district",
                }[table]
                columns = column_sql.split(",")
                values = [f":{name}" for name in params.split(",")]
                # Geometry is explicitly assigned SRID 4326 after real reprojection.
                values += [
                    "ST_SetSRID(ST_GeomFromWKB(:geom),4326)",
                    ":source_cut",
                    ":source_srid",
                    ":archive_sha256",
                    ":provenance",
                ]
                values_sql = ",".join(values)
                if table == "geo_state":
                    conflict = "state_code"
                elif table == "geo_municipality":
                    conflict = "state_code,municipality_code"
                elif table == "geo_district_2023":
                    conflict = "state_code,district_code"
                else:
                    conflict = "state_code,section_code"
                update_cols = [col for col in columns if col not in conflict.split(",")]
                update = ",".join(f"{col}=EXCLUDED.{col}" for col in update_cols)
                sql = text(
                    f"INSERT INTO {table} ({column_sql}) VALUES ({values_sql}) "
                    f"ON CONFLICT ({conflict}) DO UPDATE SET {update}"
                )
                session.execute(sql, rows)
                counts[table] += len(rows)

        pairs, split = session.execute(
            text(
                "SELECT count(*), "
                "count(DISTINCT (state_code,municipality_code)) FILTER (WHERE is_split) "
                "FROM bridge_municipality_district WHERE district_plan='DERFE2023'"
            )
        ).one()
        if (pairs, split) != (2581, 72):
            raise NationalGeographyError(
                f"Task 3 municipality-district bridge expected (2581,72), found ({pairs},{split})"
            )
        district_count = session.execute(
            text("SELECT count(*) FROM geo_district_2023")
        ).scalar_one()
        actual_labels = session.execute(
            text("SELECT count(*) FROM geo_district_2023 WHERE label LIKE 'Distrito % — %' ")
        ).scalar_one()
        if district_count != 300 or actual_labels != 300:
            raise NationalGeographyError(
                "district geometry/official labels do not cover all 300 districts"
            )

    return GeographyAudit(
        state_count=counts["geo_state"],
        municipality_count=counts["geo_municipality"],
        district_count=counts["geo_district_2023"],
        section_count=counts["geo_section"],
        archive_count=len(archives),
        source_cut=SOURCE_CUT.isoformat(),
        target_crs="EPSG:4326",
        archive_sha256=hashes,
        municipality_district_pair_count=pairs,
        split_municipality_count=split,
    )


__all__ = ["GeographyAudit", "NationalGeographyError", "import_national_cartography"]
