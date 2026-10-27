"""Repository: transactional persistence for datasets, observations and reads.

The ``Repository`` takes an already-open SQLAlchemy ``Session`` (opened by the
caller with the appropriate role). Writes are deterministic upserts keyed on the
``uuid5`` identifiers, so re-running a load never duplicates rows. All queries
are parameterised; no string is ever interpolated into SQL.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from participa_geo.db import models
from participa_geo.indicators.calculations import assess_quality, calculate_indicators
from participa_geo.ingestion.schema import (
    REFERENCE_DATE,
    DatasetVersion,
    MunicipalObservation,
    observation_id,
)

_REFERENCE_DATE = REFERENCE_DATE  # "2025-12-15"


def _escape_like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


class Repository:
    """Data access over a caller-provided ``Session``."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- writes -----------------------------------------------------------

    def upsert_dataset(self, version: DatasetVersion) -> UUID:
        """Insert or refresh one ``dataset_version`` row; returns its id."""
        stmt = pg_insert(models.DatasetVersion.__table__).values(
            id=version.id,
            year=version.year,
            source_url=version.source_url,
            member=version.member,
            sha256=version.sha256,
            encoding=version.encoding,
            publication_date=version.publication_date,
            available_at=version.available_at,
            license_conditions=version.license_conditions,
            dictionary=version.dictionary,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "source_url": stmt.excluded.source_url,
                "member": stmt.excluded.member,
                "sha256": stmt.excluded.sha256,
                "encoding": stmt.excluded.encoding,
                "publication_date": stmt.excluded.publication_date,
                "available_at": stmt.excluded.available_at,
                "license_conditions": stmt.excluded.license_conditions,
                "dictionary": stmt.excluded.dictionary,
            },
        )
        self.session.execute(stmt)
        return version.id

    def upsert_observations(self, rows: Sequence[MunicipalObservation]) -> int:
        """Upsert origin territories and observations; returns the row count.

        For every observation the deterministic origin ``territory_version``
        (NULL geometry, ``origin_year`` set) is created alongside the
        ``observation`` row. Rates and quality are derived here from the summed
        counts (single source of truth).
        """
        origin_values: list[dict] = []
        obs_values: list[dict] = []

        for obs in rows:
            origin_id = observation_id(
                obs.key.state_code, obs.key.municipality_code, obs.year
            )
            indicators = calculate_indicators(obs.ln, obs.sv, obs.nv, obs.ns)
            quality = assess_quality(obs)

            origin_values.append(
                {
                    "id": origin_id,
                    "system": "ine",
                    "state_code": obs.key.state_code,
                    "municipality_code": obs.key.municipality_code,
                    "name": obs.municipality_name,
                    "reference_date": None,
                    "origin_year": obs.year,
                    "geometry": None,
                    "source_srid": None,
                    "provenance": f"ccpc-origin-{obs.year}",
                }
            )
            obs_values.append(
                {
                    "id": origin_id,
                    "origin_territory_id": origin_id,
                    "dataset_version_id": obs.source_version_id,
                    "year": obs.year,
                    "election_type": "federal",
                    "ln": obs.ln,
                    "sv": obs.sv,
                    "nv": obs.nv,
                    "ns": obs.ns,
                    "young_share": obs.young_share,
                    "senior_share": obs.senior_share,
                    "rural_share": obs.rural_share,
                    "participation_pct": indicators.participation_pct,
                    "abstention_pct": indicators.abstention_pct,
                    "unknown_share": indicators.unknown_share,
                    "ns_lower_pct": indicators.ns_lower_pct,
                    "ns_upper_pct": indicators.ns_upper_pct,
                    "eligible": quality.eligible,
                    "quality_reasons": quality.reasons,
                }
            )

        if origin_values:
            origin_stmt = pg_insert(models.TerritoryVersion.__table__).values(origin_values)
            origin_stmt = origin_stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "name": origin_stmt.excluded.name,
                    "origin_year": origin_stmt.excluded.origin_year,
                },
            )
            self.session.execute(origin_stmt)
        if obs_values:
            obs_stmt = pg_insert(models.Observation.__table__).values(obs_values)
            obs_stmt = obs_stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "ln": obs_stmt.excluded.ln,
                    "sv": obs_stmt.excluded.sv,
                    "nv": obs_stmt.excluded.nv,
                    "ns": obs_stmt.excluded.ns,
                    "young_share": obs_stmt.excluded.young_share,
                    "senior_share": obs_stmt.excluded.senior_share,
                    "rural_share": obs_stmt.excluded.rural_share,
                    "participation_pct": obs_stmt.excluded.participation_pct,
                    "abstention_pct": obs_stmt.excluded.abstention_pct,
                    "unknown_share": obs_stmt.excluded.unknown_share,
                    "ns_lower_pct": obs_stmt.excluded.ns_lower_pct,
                    "ns_upper_pct": obs_stmt.excluded.ns_upper_pct,
                    "eligible": obs_stmt.excluded.eligible,
                    "quality_reasons": obs_stmt.excluded.quality_reasons,
                },
            )
            self.session.execute(obs_stmt)
        return len(obs_values)

    # -- reads ------------------------------------------------------------

    def get_territories(
        self,
        *,
        state_code: str,
        q: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[models.TerritoryRecord], int]:
        """Return reference municipalities (stably ordered) plus the total."""
        where = "t.reference_date = :ref_date AND t.state_code = :state_code"
        params: dict = {"ref_date": _REFERENCE_DATE, "state_code": state_code}
        if q:
            pattern = f"%{_escape_like(q)}%"
            where += (
                " AND (t.name ILIKE :q_pattern ESCAPE '!' "
                "OR t.municipality_code LIKE :q_code ESCAPE '!')"
            )
            params["q_pattern"] = pattern
            params["q_code"] = f"{_escape_like(q)}%"

        count_sql = f"SELECT count(*) FROM territory_version t WHERE {where}"
        total = int(self.session.scalar(text(count_sql), params))

        list_sql = f"""
            SELECT t.id, t.name, t.state_code, t.municipality_code, t.reference_date,
                   c.identity_status, c.footprint_status
            FROM territory_version t
            LEFT JOIN LATERAL (
                SELECT identity_status, footprint_status
                FROM territory_correspondence c
                WHERE c.reference_territory_id = t.id
                ORDER BY c.origin_territory_id
                LIMIT 1
            ) c ON true
            WHERE {where}
            ORDER BY t.municipality_code
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        rows = self.session.execute(text(list_sql), params).mappings().all()

        records = [
            models.TerritoryRecord(
                id=row["id"],
                name=row["name"],
                state_code=row["state_code"],
                municipality_code=row["municipality_code"],
                identity_status=row["identity_status"],
                footprint_status=row["footprint_status"],
                reference_date=row["reference_date"],
            )
            for row in rows
        ]
        return records, total

    def get_history(
        self,
        *,
        territory_id: UUID | None,
        year: int | None,
        page: int,
        page_size: int,
    ) -> tuple[list[models.HistoryRecord], int]:
        """Return participation history, either per territory or as state totals.

        State totals (``territory_id is None``) sum counts and recompute rates
        from the sums (never an average of municipal rates).
        """
        if territory_id is not None:
            return self._get_history_territory(territory_id, year, page, page_size)
        return self._get_history_state(year)

    def _get_history_territory(
        self, territory_id: UUID, year: int | None, page: int, page_size: int
    ) -> tuple[list[models.HistoryRecord], int]:
        where = "t_ref.id = :territory_id"
        params: dict = {"territory_id": territory_id}
        if year is not None:
            where += " AND o.year = :year"
            params["year"] = year

        count_sql = f"""
            SELECT count(*)
            FROM observation o
            JOIN territory_correspondence c ON c.origin_territory_id = o.origin_territory_id
            JOIN territory_version t_ref ON t_ref.id = c.reference_territory_id
            WHERE {where}
        """
        total = int(self.session.scalar(text(count_sql), params))

        list_sql = f"""
            SELECT t_ref.id AS territory_id, o.year, t_ref.name, t_ref.municipality_code,
                   o.ln, o.sv, o.nv, o.ns,
                   o.participation_pct, o.abstention_pct, o.unknown_share,
                   o.ns_lower_pct, o.ns_upper_pct, o.eligible,
                   c.identity_status, c.footprint_status
            FROM observation o
            JOIN territory_correspondence c ON c.origin_territory_id = o.origin_territory_id
            JOIN territory_version t_ref ON t_ref.id = c.reference_territory_id
            WHERE {where}
            ORDER BY o.year
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        rows = self.session.execute(text(list_sql), params).mappings().all()
        records = [self._history_record(row) for row in rows]
        return records, total

    def _get_history_state(self, year: int | None) -> tuple[list[models.HistoryRecord], int]:
        where = ""
        params: dict = {}
        if year is not None:
            where = "WHERE o.year = :year"
            params["year"] = year
        sql = f"""
            SELECT NULL AS territory_id, o.year, NULL AS name, NULL AS municipality_code,
                   SUM(o.ln) AS ln, SUM(o.sv) AS sv, SUM(o.nv) AS nv, SUM(o.ns) AS ns,
                   CASE WHEN SUM(o.sv) + SUM(o.nv) > 0
                        THEN 100.0 * SUM(o.sv) / (SUM(o.sv) + SUM(o.nv)) END AS participation_pct,
                   CASE WHEN SUM(o.sv) + SUM(o.nv) > 0
                        THEN 100.0 * SUM(o.nv) / (SUM(o.sv) + SUM(o.nv)) END AS abstention_pct,
                   CASE WHEN SUM(o.ln) > 0 THEN SUM(o.ns)::float / SUM(o.ln) END AS unknown_share,
                   CASE WHEN SUM(o.ln) > 0 THEN 100.0 * SUM(o.nv) / SUM(o.ln) END AS ns_lower_pct,
                   CASE WHEN SUM(o.ln) > 0 THEN 100.0 * (SUM(o.nv) + SUM(o.ns)) / SUM(o.ln)
                   END AS ns_upper_pct,
                   NULL::boolean AS eligible,
                   NULL::text AS identity_status, NULL::text AS footprint_status
            FROM observation o
            {where}
            GROUP BY o.year
            ORDER BY o.year
        """
        rows = self.session.execute(text(sql), params).mappings().all()
        records = [self._history_record(row) for row in rows]
        return records, len(records)

    @staticmethod
    def _history_record(row) -> models.HistoryRecord:
        return models.HistoryRecord(
            territory_id=row["territory_id"],
            year=row["year"],
            name=row["name"],
            municipality_code=row["municipality_code"],
            ln=row["ln"],
            sv=row["sv"],
            nv=row["nv"],
            ns=row["ns"],
            participation_pct=row["participation_pct"],
            abstention_pct=row["abstention_pct"],
            unknown_share=row["unknown_share"],
            ns_lower_pct=row["ns_lower_pct"],
            ns_upper_pct=row["ns_upper_pct"],
            eligible=row["eligible"] if row["eligible"] is not None else False,
            identity_status=row["identity_status"],
            footprint_status=row["footprint_status"],
        )


def read_processed_observations(
    processed_dir: Path,
) -> tuple[list[DatasetVersion], list[MunicipalObservation]]:
    """Read ``provenance.json`` + ``municipal-observations.parquet`` from T2.

    Returns the ``DatasetVersion`` list and the ``MunicipalObservation`` list
    that the Repository persists (shared by the ``db load`` CLI and the tests).
    """
    import json as _json
    from datetime import datetime as _datetime
    from uuid import UUID as _UUID

    import pandas as _pd

    from participa_geo.ingestion.schema import MunicipalityKey

    processed_dir = Path(processed_dir)
    provenance = _json.loads((processed_dir / "provenance.json").read_text())
    frame = _pd.read_parquet(processed_dir / "municipal-observations.parquet")

    datasets = [
        DatasetVersion(
            year=source["year"],
            source_url=source["source_url"],
            member=source["member"],
            sha256=source["sha256"],
            encoding="utf-8-sig",
            available_at=_datetime.fromisoformat(source["available_at"])
            if source.get("available_at")
            else None,
        )
        for source in provenance["sources"]
    ]

    observations: list[MunicipalObservation] = []
    for _, row in frame.iterrows():
        observations.append(
            MunicipalObservation(
                key=MunicipalityKey(
                    state_code=str(row["state_code"]),
                    municipality_code=str(row["municipality_code"]),
                ),
                year=int(row["year"]),
                ln=int(row["ln"]),
                sv=int(row["sv"]),
                nv=int(row["nv"]),
                ns=int(row["ns"]),
                municipality_name=str(row["municipality_name"]),
                young_share=_float_or_none(row["young_share"]),
                senior_share=_float_or_none(row["senior_share"]),
                rural_share=_float_or_none(row["rural_share"]),
                source_version_id=_UUID(str(row["source_version_id"])),
            )
        )
    return datasets, observations


def _float_or_none(value: object) -> float | None:
    import pandas as _pd

    if value is None or value is _pd.NA:
        return None
    try:
        if _pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return float(value)


__all__ = ["Repository", "read_processed_observations"]
