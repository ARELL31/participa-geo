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

#: Keep the read series to one observation per year while preserving every
#: dataset version for audit: the most recently loaded version for that year.
_LATEST_VERSION_FOR_YEAR = (
    "dv.id = ("
    "SELECT dv2.id FROM dataset_version dv2 "
    "JOIN observation o2 ON o2.dataset_version_id = dv2.id "
    "WHERE o2.year = o.year "
    "ORDER BY dv2.created_at DESC, dv2.id DESC LIMIT 1)"
)


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
            if obs.source_version_id is None:
                raise ValueError(
                    "observation source_version_id is required to persist a "
                    "dataset-version-scoped identity"
                )
            origin_id = observation_id(
                obs.key.state_code,
                obs.key.municipality_code,
                obs.year,
                obs.source_version_id,
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
                    "dataset_version_id": obs_stmt.excluded.dataset_version_id,
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
        return self._get_history_state(year, page, page_size)

    def _get_history_territory(
        self, territory_id: UUID, year: int | None, page: int, page_size: int
    ) -> tuple[list[models.HistoryRecord], int]:
        where = "t_ref.id = :territory_id"
        params: dict = {"territory_id": territory_id}
        if year is not None:
            where += " AND o.year = :year"
            params["year"] = year

        # Observation identities are dataset-version scoped. The history API is a
        # series (one row per year), so it reads the most recently loaded version
        # for each year while both versions remain in the database for audit.
        latest = _LATEST_VERSION_FOR_YEAR

        count_sql = f"""
            SELECT count(*)
            FROM observation o
            JOIN dataset_version dv ON dv.id = o.dataset_version_id
            JOIN territory_correspondence c ON c.origin_territory_id = o.origin_territory_id
            JOIN territory_version t_ref ON t_ref.id = c.reference_territory_id
            WHERE {where} AND {latest}
        """
        total = int(self.session.scalar(text(count_sql), params))

        list_sql = f"""
            SELECT t_ref.id AS territory_id, o.year, t_ref.name, t_ref.municipality_code,
                   o.ln, o.sv, o.nv, o.ns,
                   o.participation_pct, o.abstention_pct, o.unknown_share,
                   o.ns_lower_pct, o.ns_upper_pct, o.eligible,
                   c.identity_status, c.footprint_status
            FROM observation o
            JOIN dataset_version dv ON dv.id = o.dataset_version_id
            JOIN territory_correspondence c ON c.origin_territory_id = o.origin_territory_id
            JOIN territory_version t_ref ON t_ref.id = c.reference_territory_id
            WHERE {where} AND {latest}
            ORDER BY o.year
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        rows = self.session.execute(text(list_sql), params).mappings().all()
        records = [self._history_record(row) for row in rows]
        return records, total

    def _get_history_state(
        self, year: int | None, page: int, page_size: int
    ) -> tuple[list[models.HistoryRecord], int]:
        where = ""
        params: dict = {}
        if year is not None:
            where = "WHERE o.year = :year"
            params["year"] = year
        latest = _LATEST_VERSION_FOR_YEAR
        count_sql = f"""
            SELECT count(DISTINCT o.year)
            FROM observation o
            JOIN dataset_version dv ON dv.id = o.dataset_version_id
            {where} {"AND" if where else "WHERE"} {latest}
        """
        total = int(self.session.scalar(text(count_sql), params))
        sql = f"""
            SELECT NULL AS territory_id, o.year, NULL AS name, NULL AS municipality_code,
                   SUM(o.ln) AS ln, SUM(o.sv) AS sv, SUM(o.nv) AS nv, SUM(o.ns) AS ns,
                   CASE WHEN SUM(o.sv) + SUM(o.nv) > 0
                        THEN (100.0 * SUM(o.sv) / (SUM(o.sv) + SUM(o.nv)))::float8
                   END AS participation_pct,
                   CASE WHEN SUM(o.sv) + SUM(o.nv) > 0
                        THEN (100.0 * SUM(o.nv) / (SUM(o.sv) + SUM(o.nv)))::float8
                   END AS abstention_pct,
                   CASE WHEN SUM(o.ln) > 0
                        THEN (SUM(o.ns)::float8 / SUM(o.ln))::float8 END AS unknown_share,
                   CASE WHEN SUM(o.ln) > 0
                        THEN (100.0 * SUM(o.nv) / SUM(o.ln))::float8 END AS ns_lower_pct,
                   CASE WHEN SUM(o.ln) > 0
                        THEN (100.0 * (SUM(o.nv) + SUM(o.ns)) / SUM(o.ln))::float8
                   END AS ns_upper_pct,
                   NULL::boolean AS eligible,
                   NULL::text AS identity_status, NULL::text AS footprint_status
            FROM observation o
            JOIN dataset_version dv ON dv.id = o.dataset_version_id
            {where} {"AND" if where else "WHERE"} {latest}
            GROUP BY o.year
            ORDER BY o.year
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        rows = self.session.execute(text(sql), params).mappings().all()
        records = [self._history_record(row) for row in rows]
        return records, total

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

    # -- model / prediction reads -----------------------------------------

    def get_dataset_version_ids(self) -> list[UUID]:
        """Return every loaded dataset version id (ascending year)."""
        rows = self.session.execute(
            text("SELECT id FROM dataset_version ORDER BY year")
        ).scalars().all()
        return [UUID(str(r)) for r in rows]

    def get_models(
        self, *, page: int, page_size: int
    ) -> tuple[list[models.ModelRecord], int]:
        """Return the loaded model runs (most recent first) plus the total."""
        total = int(self.session.scalar(text("SELECT count(*) FROM model_run")))
        rows = self.session.execute(
            text(
                """
                SELECT id, family, parameters, features, cut_dates, hashes,
                       dependencies, metrics, exclusions, created_at
                FROM model_run
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": page_size, "offset": (page - 1) * page_size},
        ).mappings().all()
        return [self._model_record(row) for row in rows], total

    def get_model(self, model_run_id: UUID) -> models.ModelRecord | None:
        """Return one model run by id, or ``None`` when absent."""
        row = self.session.execute(
            text(
                """
                SELECT id, family, parameters, features, cut_dates, hashes,
                       dependencies, metrics, exclusions, created_at
                FROM model_run
                WHERE id = :id
                """
            ),
            {"id": model_run_id},
        ).mappings().first()
        return self._model_record(row) if row else None

    def get_published_model_run_id(self) -> UUID | None:
        """Return the most recently loaded model run id (the deployed model)."""
        row = self.session.execute(
            text("SELECT id FROM model_run ORDER BY created_at DESC LIMIT 1")
        ).first()
        return row[0] if row else None

    def get_predictions(
        self,
        *,
        model_run_id: UUID,
        target_year: int,
        territory_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[models.PredictionRecord], int]:
        """Return prediction rows (stably ordered by municipality code)."""
        where = "p.model_run_id = :model_run_id AND p.target_year = :target_year"
        params: dict = {"model_run_id": model_run_id, "target_year": target_year}
        if territory_id is not None:
            where += " AND p.reference_territory_id = :territory_id"
            params["territory_id"] = territory_id

        total = int(
            self.session.scalar(
                text(f"SELECT count(*) FROM prediction p WHERE {where}"), params
            )
        )

        list_sql = f"""
            SELECT p.reference_territory_id AS territory_id,
                   t.municipality_code, t.name AS municipality_name,
                   p.target_year, p.estimated_abstention_pct,
                   p.historical_error_lower_pct, p.historical_error_upper_pct,
                   p.risk, p.risk_unstable, p.eligible, p.quality, p.model_run_id
            FROM prediction p
            JOIN territory_version t ON t.id = p.reference_territory_id
            WHERE {where}
            ORDER BY t.municipality_code
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        rows = self.session.execute(text(list_sql), params).mappings().all()
        return [self._prediction_record(row) for row in rows], total

    @staticmethod
    def _model_record(row) -> models.ModelRecord:
        return models.ModelRecord(
            model_run_id=row["id"],
            family=row["family"],
            parameters=row["parameters"],
            features=row["features"],
            cut_dates=row["cut_dates"],
            hashes=row["hashes"],
            dependencies=row["dependencies"],
            metrics=row["metrics"],
            exclusions=row["exclusions"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _prediction_record(row) -> models.PredictionRecord:
        return models.PredictionRecord(
            territory_id=row["territory_id"],
            municipality_code=row["municipality_code"],
            municipality_name=row["municipality_name"],
            target_year=row["target_year"],
            estimated_abstention_pct=row["estimated_abstention_pct"],
            historical_error_lower_pct=row["historical_error_lower_pct"],
            historical_error_upper_pct=row["historical_error_upper_pct"],
            risk=row["risk"],
            risk_unstable=row["risk_unstable"],
            eligible=row["eligible"],
            quality=row["quality"],
            model_run_id=row["model_run_id"],
        )

    # -- scenario writes / reads ------------------------------------------

    def insert_scenario(self, scenario: models.ScenarioRecord) -> None:
        """Insert one scenario header (the caller owns the transaction)."""
        self.session.execute(
            pg_insert(models.Scenario.__table__).values(
                id=scenario.scenario_id,
                model_run_id=scenario.model_run_id,
                target_year=scenario.target_year,
                reduction_pp=scenario.requested_reduction_pp,
                assumption_code=scenario.assumption_code,
                assumption_version=scenario.assumption_version,
                rationale_text=scenario.rationale_text,
                rules_version=scenario.rules_version,
                input_sha256=scenario.input_sha256,
                model_sha256=scenario.model_sha256,
                selection=scenario.selection,
                created_at=scenario.created_at,
            )
        )

    def insert_scenario_results(
        self,
        scenario_id: UUID,
        results: Sequence[models.ScenarioResultRecord],
    ) -> None:
        """Insert the 125 municipality results in the caller's transaction."""
        if not results:
            return
        from uuid import NAMESPACE_URL as _NAMESPACE_URL
        from uuid import uuid5 as _uuid5

        values = [
            {
                "id": _uuid5(
                    _NAMESPACE_URL,
                    f"participa-geo:scenario-result:{scenario_id}:{result.territory_id}",
                ),
                "scenario_id": scenario_id,
                "reference_territory_id": result.territory_id,
                "baseline_abstention_pct": result.baseline_abstention_pct,
                "hypothetical_abstention_pct": result.hypothetical_abstention_pct,
                "baseline_error_lower_pct": result.baseline_error_lower_pct,
                "baseline_error_upper_pct": result.baseline_error_upper_pct,
                "hypothetical_error_lower_pct": result.hypothetical_error_lower_pct,
                "hypothetical_error_upper_pct": result.hypothetical_error_upper_pct,
                "requested_reduction_pp": result.requested_reduction_pp,
                "effective_reduction_pp": result.effective_reduction_pp,
                "risk_a": result.risk_a,
                "risk_b": result.risk_b,
                "risk_a_unstable": result.risk_a_unstable,
                "risk_b_unstable": result.risk_b_unstable,
                "selected": result.selected,
            }
            for result in results
        ]
        self.session.execute(pg_insert(models.ScenarioResult.__table__).values(values))

    def get_scenario(
        self, scenario_id: UUID
    ) -> tuple[models.ScenarioRecord, list[models.ScenarioResultRecord]] | None:
        """Return a persisted scenario and its results, or ``None`` when absent.

        This is a pure read: it never recomputes A/B from the current model.
        """
        row = self.session.execute(
            text(
                """
                SELECT id AS scenario_id, model_run_id, target_year, reduction_pp,
                       assumption_code, assumption_version, rationale_text,
                       rules_version, input_sha256, model_sha256, selection,
                       created_at
                FROM scenario
                WHERE id = :scenario_id
                """
            ),
            {"scenario_id": scenario_id},
        ).mappings().first()
        if row is None:
            return None

        scenario = models.ScenarioRecord(
            scenario_id=row["scenario_id"],
            model_run_id=row["model_run_id"],
            target_year=row["target_year"],
            requested_reduction_pp=float(row["reduction_pp"]),
            assumption_code=row["assumption_code"],
            assumption_version=row["assumption_version"],
            rationale_text=row["rationale_text"],
            rules_version=row["rules_version"],
            input_sha256=row["input_sha256"],
            model_sha256=row["model_sha256"],
            selection=[str(value) for value in (row["selection"] or [])],
            created_at=row["created_at"],
        )

        result_rows = self.session.execute(
            text(
                """
                SELECT s.scenario_id, s.reference_territory_id AS territory_id,
                       t.municipality_code, t.name AS municipality_name,
                       s.baseline_abstention_pct, s.hypothetical_abstention_pct,
                       s.baseline_error_lower_pct, s.baseline_error_upper_pct,
                       s.hypothetical_error_lower_pct,
                       s.hypothetical_error_upper_pct,
                       s.requested_reduction_pp, s.effective_reduction_pp,
                       s.risk_a, s.risk_b, s.risk_a_unstable, s.risk_b_unstable,
                       s.selected
                FROM scenario_result s
                JOIN territory_version t ON t.id = s.reference_territory_id
                WHERE s.scenario_id = :scenario_id
                ORDER BY t.municipality_code
                """
            ),
            {"scenario_id": scenario_id},
        ).mappings().all()

        results = [
            models.ScenarioResultRecord(
                scenario_id=result["scenario_id"],
                territory_id=result["territory_id"],
                municipality_code=result["municipality_code"],
                municipality_name=result["municipality_name"],
                baseline_abstention_pct=result["baseline_abstention_pct"],
                hypothetical_abstention_pct=result["hypothetical_abstention_pct"],
                baseline_error_lower_pct=result["baseline_error_lower_pct"],
                baseline_error_upper_pct=result["baseline_error_upper_pct"],
                hypothetical_error_lower_pct=result[
                    "hypothetical_error_lower_pct"
                ],
                hypothetical_error_upper_pct=result[
                    "hypothetical_error_upper_pct"
                ],
                requested_reduction_pp=float(result["requested_reduction_pp"]),
                effective_reduction_pp=float(result["effective_reduction_pp"]),
                risk_a=result["risk_a"] or "insufficient",
                risk_b=result["risk_b"] or "insufficient",
                risk_a_unstable=bool(result["risk_a_unstable"]),
                risk_b_unstable=bool(result["risk_b_unstable"]),
                selected=bool(result["selected"]),
            )
            for result in result_rows
        ]
        return scenario, results


def load_model_bundle(path: Path, session: Session) -> UUID:
    """Load the T4 artifact bundle into ``model_run`` + ``prediction`` rows.

    Reads ``model.json``, ``evaluation.json``, ``manifest.json`` and
    ``predictions-2027.parquet`` (never pickle/joblib, never retrains). The
    ``model_run_id`` is taken from the artifact truth; upserts are keyed on
    deterministic ids, so re-loading identical content is idempotent and inserts
    exactly 125 prediction rows. Returns the loaded ``model_run_id``.
    """
    import json as _json
    from uuid import NAMESPACE_URL as _NAMESPACE_URL
    from uuid import uuid5 as _uuid5

    import pandas as _pd

    path = Path(path)
    model_payload = _json.loads((path / "model.json").read_text(encoding="utf-8"))
    evaluation_payload = _json.loads(
        (path / "evaluation.json").read_text(encoding="utf-8")
    )
    manifest_payload = _json.loads((path / "manifest.json").read_text(encoding="utf-8"))

    model_run_id = UUID(str(model_payload["model_run_id"]))
    family = str(model_payload["family"])
    target_year = int(model_payload["target_year"])
    reference_date = str(model_payload.get("reference_date", "2025-12-15"))
    feature_order = list(model_payload.get("feature_order", []))

    parameters: dict = {
        "alpha": model_payload.get("alpha"),
        "feature_order": feature_order,
        "description": model_payload.get("description"),
        "limitations": list(model_payload.get("limitations", [])),
        "clipped_count_2027": model_payload.get("clipped_count_2027"),
    }
    if model_payload.get("candidate_m1") is not None:
        parameters["candidate_m1"] = model_payload["candidate_m1"]
    for key in ("intercept", "coefficients", "scaler"):
        if model_payload.get(key) is not None:
            parameters[key] = model_payload[key]
    for key in (
        "explanations",
        "candidate_m1_explanations",
        "features_2027",
    ):
        if model_payload.get(key) is not None:
            parameters[key] = model_payload[key]

    cut_dates: dict = {
        "reference_date": reference_date,
        "target_year": target_year,
        "validation_year": evaluation_payload.get("validation_year"),
        "test_year": evaluation_payload.get("test_year"),
        "fit_years": [2015, 2018, 2021, 2024],
    }

    hashes: dict = {
        "data_aggregate_sha256": manifest_payload.get("data_aggregate_sha256"),
        "logical_hash": manifest_payload.get("logical_hash"),
        "artifacts": manifest_payload.get("artifacts", {}),
    }

    dependencies: dict = manifest_payload.get("versions", {})

    metrics: dict = {
        "selected_family": evaluation_payload.get("selected_family"),
        "validation_year": evaluation_payload.get("validation_year"),
        "test_year": evaluation_payload.get("test_year"),
        "selection": evaluation_payload.get("selection", {}),
        "metrics": evaluation_payload.get("metrics", {}),
        "band": evaluation_payload.get("band", {}),
        "cohorts": evaluation_payload.get("cohorts", {}),
    }

    exclusions: dict = evaluation_payload.get("exclusions", {})

    stmt = pg_insert(models.ModelRun.__table__).values(
        id=model_run_id,
        family=family,
        parameters=parameters,
        features=feature_order,
        cut_dates=cut_dates,
        hashes=hashes,
        dependencies=dependencies,
        metrics=metrics,
        exclusions=exclusions,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "family": stmt.excluded.family,
            "parameters": stmt.excluded.parameters,
            "features": stmt.excluded.features,
            "cut_dates": stmt.excluded.cut_dates,
            "hashes": stmt.excluded.hashes,
            "dependencies": stmt.excluded.dependencies,
            "metrics": stmt.excluded.metrics,
            "exclusions": stmt.excluded.exclusions,
        },
    )
    session.execute(stmt)

    frame = _pd.read_parquet(path / "predictions-2027.parquet")
    prediction_rows: list[dict] = []
    for _, row in frame.iterrows():
        territory_id = UUID(str(row["territory_id"]))
        target = int(row["target_year"])
        prediction_id = _uuid5(
            _NAMESPACE_URL,
            f"participa-geo:prediction:{model_run_id}:{territory_id}:{target}",
        )
        quality = _prediction_quality_dict(row)
        prediction_rows.append(
            {
                "id": prediction_id,
                "model_run_id": model_run_id,
                "reference_territory_id": territory_id,
                "target_year": target,
                "estimated_abstention_pct": _float_or_none(
                    row["estimated_abstention_pct"]
                ),
                "historical_error_lower_pct": _float_or_none(
                    row["historical_error_lower_pct"]
                ),
                "historical_error_upper_pct": _float_or_none(
                    row["historical_error_upper_pct"]
                ),
                "risk": str(row["risk"]) if row["risk"] is not None else None,
                "risk_unstable": bool(row["risk_unstable"])
                if row["risk_unstable"] is not None
                else False,
                "eligible": bool(row["eligible"]),
                "quality": quality,
            }
        )

    if prediction_rows:
        pred_stmt = pg_insert(models.Prediction.__table__).values(prediction_rows)
        pred_stmt = pred_stmt.on_conflict_do_update(
            index_elements=["model_run_id", "reference_territory_id", "target_year"],
            set_={
                "estimated_abstention_pct": pred_stmt.excluded.estimated_abstention_pct,
                "historical_error_lower_pct": pred_stmt.excluded.historical_error_lower_pct,
                "historical_error_upper_pct": pred_stmt.excluded.historical_error_upper_pct,
                "risk": pred_stmt.excluded.risk,
                "risk_unstable": pred_stmt.excluded.risk_unstable,
                "eligible": pred_stmt.excluded.eligible,
                "quality": pred_stmt.excluded.quality,
            },
        )
        session.execute(pred_stmt)

    return model_run_id


def _prediction_quality_dict(row) -> dict | None:
    """Reconstruct the quality JSON from the prediction parquet row."""
    import json as _json

    quality = row.get("quality")
    if isinstance(quality, str):
        return _json.loads(quality)
    if isinstance(quality, dict):
        return quality
    # Fall back to the denormalised columns when the JSON blob is absent.
    reasons_raw = row.get("quality_reasons")
    reasons = (
        [str(r) for r in str(reasons_raw).split(";") if str(r).strip()]
        if reasons_raw is not None
        else []
    )
    return {
        "eligible": bool(row.get("eligible")),
        "reasons": reasons,
        "identity_status": (
            str(row["identity_status"]) if row.get("identity_status") is not None else None
        ),
        "footprint_status": (
            str(row["footprint_status"]) if row.get("footprint_status") is not None else None
        ),
    }


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


__all__ = ["Repository", "load_model_bundle", "read_processed_observations"]
