"""Real delivery context derived from the T2/T4 artifacts and a persisted scenario.

Nothing here is a template of invented numbers: the counts, metrics, versions,
sources and limitations are read from ``municipal-observations.parquet``,
``quality.json``, ``provenance.json``, ``model.json``, ``evaluation.json``,
``manifest.json`` and ``predictions-2027.parquet``. A scenario (when supplied)
comes from the persisted database row.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from participa_geo.api.schemas.scenarios import ScenarioDTO
from participa_geo.reporting.tables import (
    history_dictionary_csv,
    scenario_dictionary_csv,
)


def repo_root() -> Path:
    """Find the repository root without relying on the current directory."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


@dataclass(frozen=True)
class SourceFact:
    year: int
    source_url: str
    member: str
    sha256: str
    municipality_count: int | None = None
    ln: int | None = None


@dataclass(frozen=True)
class ModelFacts:
    family: str
    model_run_id: UUID
    validation_year: int
    test_year: int
    mae_2021: float
    m1_mae_2021: float
    mae_2024: float
    m1_mae_2024: float
    band_pp: float
    band_n: int
    n_validation: int
    n_test: int
    feature_order: tuple[str, ...]
    limitations: tuple[str, ...]
    empirical_coverage_2024: dict | None = None
    candidate_m1: dict | None = None


@dataclass(frozen=True)
class ExclusionFact:
    """One excluded municipality and its stable reasons for a cut."""

    municipality_code: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CohortFacts:
    total: int
    eligible: int
    insufficient: int
    unstable: int
    eligible_ln: int
    total_ln: int
    risk_counts: dict[str, int] = field(default_factory=dict)
    baseline_min: float | None = None
    baseline_median: float | None = None
    baseline_max: float | None = None
    eligible_by_year: dict[int, int] = field(default_factory=dict)
    excluded_by_year: dict[int, int] = field(default_factory=dict)
    #: Year whose observed LN is the coverage denominator for 2027 (2024).
    ln_coverage_base_year: int | None = None
    #: Per-cut excluded municipalities and their reasons (Spec §7).
    exclusion_details: dict[int, tuple[ExclusionFact, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioFacts:
    scenario_id: UUID
    model_run_id: UUID
    model_sha256: str
    input_sha256: str
    target_year: int
    requested_reduction_pp: float
    #: Retained for compatibility: the maximum effective reduction in the selection.
    effective_reduction_pp: float
    effective_reduction_min_pp: float
    effective_reduction_max_pp: float
    assumption_code: str
    assumption_version: str
    rationale_text: str
    rules_version: str
    error_band_label: str
    selected_count: int
    risk_a_counts: dict[str, int]
    risk_b_counts: dict[str, int]
    risk_a_unstable: int
    risk_b_unstable: int
    baseline_mean: float | None
    hypothetical_mean: float | None


@dataclass(frozen=True)
class DeliveryContext:
    generated_at: datetime
    reference_date: str
    data_aggregate_sha256: str
    versions: dict[str, str]
    model: ModelFacts
    cohort: CohortFacts
    sources: tuple[SourceFact, ...]
    dataset_version_ids: tuple[UUID, ...]
    exclusions: dict[int, int]
    exclusion_details: dict[int, tuple[ExclusionFact, ...]]
    limitations: tuple[str, ...]
    scenario: ScenarioFacts | None = None
    team_slug: str = "participa-geo"
    eje: str = "Participación y territorio"
    national: bool = False


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _float(value: Any) -> float:
    return float(value)


def _scenario_facts(scenario: ScenarioDTO) -> ScenarioFacts:
    results = scenario.results
    selected = [row for row in results if row.selected]
    baseline_values = [
        row.baseline_abstention_pct for row in selected if row.baseline_abstention_pct is not None
    ]
    hypothetical_values = [
        row.hypothetical_abstention_pct
        for row in selected
        if row.hypothetical_abstention_pct is not None
    ]
    risk_a_counts = {
        key: sum(1 for row in results if row.risk_a == key)
        for key in ("low", "medium", "high", "insufficient")
    }
    risk_b_counts = {
        key: sum(1 for row in results if row.risk_b == key)
        for key in ("low", "medium", "high", "insufficient")
    }
    effective_values = [row.effective_reduction_pp for row in selected]
    effective_min = min(effective_values, default=0.0)
    effective_max = max(effective_values, default=0.0)
    return ScenarioFacts(
        scenario_id=scenario.scenario_id,
        model_run_id=scenario.model_run_id,
        model_sha256=scenario.model_sha256,
        input_sha256=scenario.input_sha256,
        target_year=scenario.target_year,
        requested_reduction_pp=scenario.requested_reduction_pp,
        effective_reduction_pp=effective_max,
        effective_reduction_min_pp=effective_min,
        effective_reduction_max_pp=effective_max,
        assumption_code=scenario.assumption_code,
        assumption_version=scenario.assumption_version,
        rationale_text=scenario.rationale_text,
        rules_version=scenario.rules_version,
        error_band_label=scenario.error_band_label,
        selected_count=len(selected),
        risk_a_counts=risk_a_counts,
        risk_b_counts=risk_b_counts,
        risk_a_unstable=sum(1 for row in results if row.risk_a_unstable),
        risk_b_unstable=sum(1 for row in results if row.risk_b_unstable),
        baseline_mean=(sum(baseline_values) / len(baseline_values) if baseline_values else None),
        hypothetical_mean=(
            sum(hypothetical_values) / len(hypothetical_values) if hypothetical_values else None
        ),
    )


def load_delivery_context(
    model_dir: Path | str | None = None,
    processed_dir: Path | str | None = None,
    *,
    scenario: ScenarioDTO | None = None,
    generated_at: datetime | None = None,
) -> DeliveryContext:
    """Build the immutable facts shared by the methodology/executive documents."""
    import pandas as pd

    root = repo_root()
    processed = Path(processed_dir) if processed_dir else root / "data" / "processed"
    national_processed = processed / "national"
    national_model = national_processed / "model"
    explicit_model = Path(model_dir) if model_dir else None
    is_national = national_model.is_dir() and (
        model_dir is None
        or explicit_model is None
        or explicit_model.resolve() == national_model.resolve()
        or not (explicit_model / "manifest.json").is_file()
    )
    if is_national:
        processed = national_processed
    model_dir = (
        explicit_model if explicit_model and explicit_model.is_dir() else processed / "model"
    )

    manifest = _read_json(model_dir / "manifest.json")
    evaluation = _read_json(model_dir / "evaluation.json")
    model = _read_json(model_dir / "model.json")
    provenance_path = processed / ("national-ingest.json" if is_national else "provenance.json")
    provenance = _read_json(provenance_path)
    predictions = pd.read_parquet(model_dir / "predictions-2027.parquet")

    total = len(predictions)
    eligible = int(predictions["eligible"].fillna(False).sum())
    insufficient = total - eligible
    if "risk_unstable" in predictions:
        unstable = int(
            predictions.loc[predictions["eligible"].fillna(False), "risk_unstable"]
            .fillna(False)
            .sum()
        )
    elif {"historical_error_lower_pct", "historical_error_upper_pct"}.issubset(predictions.columns):
        eligible_predictions = predictions.loc[predictions["eligible"].fillna(False)]
        unstable = int(
            (
                (
                    (eligible_predictions["historical_error_lower_pct"] < 40)
                    & (eligible_predictions["historical_error_upper_pct"] >= 40)
                )
                | (
                    (eligible_predictions["historical_error_lower_pct"] < 50)
                    & (eligible_predictions["historical_error_upper_pct"] >= 50)
                )
            ).sum()
        )
    else:
        unstable = 0
    risk_counts = {
        key: int((predictions["risk"].fillna("insufficient") == key).sum())
        for key in ("low", "medium", "high", "insufficient")
    }
    baseline_values = predictions.loc[
        predictions["eligible"].fillna(False), "estimated_abstention_pct"
    ].dropna()
    eligible_ln = int(
        predictions.loc[predictions["eligible"].fillna(False), "estimated_abstention_pct"]
        .notna()
        .sum()
    )
    # LN coverage is not in the prediction artifact; use the evaluation cohort.
    cohorts = evaluation.get("cohorts", {})
    cohort_2027 = cohorts.get("2027", {})
    eligible_ln_value = int(cohort_2027.get("eligible_ln", 0))
    total_ln_value = int(cohort_2027.get("total_ln", 0))
    if is_national and processed.joinpath("municipal-observations.csv").is_file():
        observations_2024 = pd.read_csv(processed / "municipal-observations.csv")
        observations_2024 = observations_2024.loc[observations_2024["year"] == 2024]
        total_ln_value = int(observations_2024["ln"].fillna(0).sum())
        eligible_predictions = predictions.loc[predictions["eligible"].fillna(False)]
        eligible_keys = set(
            zip(
                eligible_predictions["state_code"].astype(str).str.zfill(2),
                eligible_predictions["municipality_code"].astype(str).str.zfill(3),
                strict=True,
            )
        )
        observations_2024["state_code"] = observations_2024["state_code"].astype(str).str.zfill(2)
        observations_2024["municipality_code"] = (
            observations_2024["municipality_code"].astype(str).str.zfill(3)
        )
        eligible_mask = observations_2024.apply(
            lambda row: (row["state_code"], row["municipality_code"]) in eligible_keys,
            axis=1,
        )
        eligible_ln_value = int(observations_2024.loc[eligible_mask, "ln"].fillna(0).sum())
    eligible_by_year = {
        int(year): int(values.get("eligible_count", 0))
        for year, values in cohorts.items()
        if str(year).isdigit()
    }
    excluded_by_year = {
        int(year): int(values.get("excluded_count", 0))
        for year, values in cohorts.items()
        if str(year).isdigit()
    }
    exclusion_details = {
        int(year): tuple(
            ExclusionFact(
                municipality_code=str(item.get("municipality_code", "")),
                reasons=tuple(str(reason) for reason in item.get("reasons", [])),
            )
            for item in values
        )
        for year, values in (evaluation.get("exclusions") or {}).items()
        if str(year).isdigit()
    }
    ln_coverage_base_year = cohort_2027.get("ln_coverage_base_year")
    ln_coverage_base_year = (
        int(ln_coverage_base_year) if ln_coverage_base_year is not None else None
    )

    metrics = evaluation.get("metrics", {})
    m0 = metrics.get("m0", {})
    m1 = metrics.get("m1", {})
    validation_year = int(evaluation.get("validation_year", 2021))
    test_year = int(evaluation.get("test_year", 2024))
    band = evaluation.get("band", {})
    selection = evaluation.get("selection", {})

    if is_national:
        inventory_path = root / "data" / "sources-national.json"
        inventory = _read_json(inventory_path) if inventory_path.is_file() else {}
        source_by_year = {int(item["year"]): item for item in inventory.get("sources", [])}
        ingest_by_year = {int(item["year"]): item for item in provenance.get("sources", [])}
        csv_by_year: dict[int, list[dict]] = {}
        for year_fact in provenance.get("sources", []):
            members = year_fact.get("csv_members", [])
            if not members:
                continue
            try:
                year = int(str(members[0].get("member", "")).split("ConteosCensales", 1)[1][:4])
            except (IndexError, ValueError):
                continue
            csv_by_year[year] = members
        sources = tuple(
            SourceFact(
                year=year,
                source_url=str(source_by_year.get(year, {}).get("source_url", "")),
                member=str(source_by_year.get(year, {}).get("zip", "")),
                sha256=str(ingest_by_year.get(year, {}).get("zip_sha256") or ""),
                municipality_count=int(provenance.get("municipality_count", 0)),
                ln=None,
            )
            for year in sorted(csv_by_year)
        )
    else:
        sources = tuple(
            SourceFact(
                year=int(source.get("year", 0)),
                source_url=str(source.get("source_url", "")),
                member=str(source.get("member", "")),
                sha256=str(source.get("sha256", "")),
                municipality_count=source.get("municipality_count"),
                ln=(source.get("totals") or {}).get("ln"),
            )
            for source in sorted(
                provenance.get("sources", []), key=lambda item: int(item.get("year", 0))
            )
        )

    limitations = tuple(
        dict.fromkeys(
            list(manifest.get("limitations", []))
            + list(model.get("limitations", []))
            + [
                "Los conteos CCPC excluyen casillas especiales y residentes en el extranjero; "
                "sus tasas no son cómputos electorales oficiales.",
                "La referencia cartográfica es 2025-12-15; footprint_status=not_verified: "
                "no se promete igualdad histórica de límites.",
                "El semáforo es analítico, no una clasificación oficial del INE.",
            ]
        )
    )

    return DeliveryContext(
        generated_at=generated_at or datetime.now(UTC),
        reference_date=str(manifest.get("reference_date", "2025-12-15")),
        data_aggregate_sha256=str(
            manifest.get("data_aggregate_sha256") or provenance.get("aggregate_sha256", "")
        ),
        versions={str(k): str(v) for k, v in (manifest.get("versions") or {}).items()},
        model=ModelFacts(
            family=str(evaluation.get("selected_family", model.get("family", "M0"))),
            model_run_id=UUID(str(manifest.get("model_run_id", model.get("model_run_id")))),
            validation_year=validation_year,
            test_year=test_year,
            mae_2021=_float(
                m0.get(str(validation_year), {}).get("mae", selection.get("m0_mae_2021", 0.0))
            ),
            m1_mae_2021=_float(
                m1.get(str(validation_year), {}).get("mae", selection.get("m1_mae_2021", 0.0))
            ),
            mae_2024=_float(m0.get(str(test_year), {}).get("mae", 0.0)),
            m1_mae_2024=_float(m1.get(str(test_year), {}).get("mae", 0.0)),
            band_pp=_float(band.get("amplitude_pp", 0.0)),
            band_n=int(band.get("n_errors_2021", 0)),
            n_validation=int(m0.get(str(validation_year), {}).get("n", 0)),
            n_test=int(m0.get(str(test_year), {}).get("n", 0)),
            feature_order=tuple(model.get("feature_order", [])),
            limitations=tuple(model.get("limitations", [])),
            empirical_coverage_2024=band.get("empirical_coverage_2024"),
            candidate_m1=model.get("candidate_m1") or model.get("candidate_m1_2021"),
        ),
        cohort=CohortFacts(
            total=total,
            eligible=eligible,
            insufficient=insufficient,
            unstable=unstable,
            eligible_ln=eligible_ln_value or eligible_ln,
            total_ln=total_ln_value,
            risk_counts=risk_counts,
            baseline_min=float(baseline_values.min()) if not baseline_values.empty else None,
            baseline_median=float(baseline_values.median()) if not baseline_values.empty else None,
            baseline_max=float(baseline_values.max()) if not baseline_values.empty else None,
            eligible_by_year=eligible_by_year,
            excluded_by_year=excluded_by_year,
            ln_coverage_base_year=ln_coverage_base_year,
            exclusion_details=exclusion_details,
        ),
        sources=sources,
        dataset_version_ids=tuple(
            UUID(str(version_id))
            for version_id in (
                [
                    member.get("dataset_version_id")
                    for year_source in provenance.get("sources", [])
                    for member in year_source.get("csv_members", [])
                ]
                if is_national
                else [source.get("source_version_id") for source in provenance.get("sources", [])]
            )
            if version_id
        ),
        exclusions={
            int(year): len(values)
            for year, values in (evaluation.get("exclusions") or {}).items()
            if str(year).isdigit()
        },
        exclusion_details=exclusion_details,
        limitations=limitations,
        scenario=_scenario_facts(scenario) if scenario is not None else None,
        national=is_national,
    )


def context_manifest(context: DeliveryContext) -> dict:
    """A compact, machine-readable summary embedded in PDFs and the ZIP."""
    payload: dict = {
        "team_slug": context.team_slug,
        "eje": context.eje,
        "generated_at": context.generated_at.isoformat(),
        "reference_date": context.reference_date,
        "data_aggregate_sha256": context.data_aggregate_sha256,
        "versions": context.versions,
        "dataset_version_ids": [str(item) for item in context.dataset_version_ids],
        "model": {
            "family": context.model.family,
            "model_run_id": str(context.model.model_run_id),
            "validation_year": context.model.validation_year,
            "test_year": context.model.test_year,
            "mae_2021": context.model.mae_2021,
            "m1_mae_2021": context.model.m1_mae_2021,
            "mae_2024": context.model.mae_2024,
            "m1_mae_2024": context.model.m1_mae_2024,
            "band_pp": context.model.band_pp,
            "band_n": context.model.band_n,
            "empirical_coverage_2024": context.model.empirical_coverage_2024,
        },
        "cohort": {
            "total": context.cohort.total,
            "eligible": context.cohort.eligible,
            "insufficient": context.cohort.insufficient,
            "unstable": context.cohort.unstable,
            "eligible_ln": context.cohort.eligible_ln,
            "total_ln": context.cohort.total_ln,
            "risk_counts": context.cohort.risk_counts,
            "baseline_min": context.cohort.baseline_min,
            "baseline_median": context.cohort.baseline_median,
            "baseline_max": context.cohort.baseline_max,
            "eligible_by_year": context.cohort.eligible_by_year,
            "excluded_by_year": context.cohort.excluded_by_year,
            "ln_coverage_base_year": context.cohort.ln_coverage_base_year,
            "exclusion_reasons_by_year": {
                str(year): {
                    reason: sum(1 for fact in facts if reason in fact.reasons)
                    for reason in sorted({reason for fact in facts for reason in fact.reasons})
                }
                for year, facts in context.exclusion_details.items()
            },
        },
        "sources": [
            {
                "year": source.year,
                "source_url": source.source_url,
                "member": source.member,
                "sha256": source.sha256,
                "municipality_count": source.municipality_count,
                "ln": source.ln,
            }
            for source in context.sources
        ],
        "limitations": list(context.limitations),
    }
    if context.scenario is not None:
        scenario = context.scenario
        payload["scenario"] = {
            "scenario_id": str(scenario.scenario_id),
            "model_run_id": str(scenario.model_run_id),
            "model_sha256": scenario.model_sha256,
            "input_sha256": scenario.input_sha256,
            "target_year": scenario.target_year,
            "requested_reduction_pp": scenario.requested_reduction_pp,
            "effective_reduction_pp": scenario.effective_reduction_pp,
            "effective_reduction_min_pp": scenario.effective_reduction_min_pp,
            "effective_reduction_max_pp": scenario.effective_reduction_max_pp,
            "assumption_code": scenario.assumption_code,
            "assumption_version": scenario.assumption_version,
            "rationale_text": scenario.rationale_text,
            "rules_version": scenario.rules_version,
            "error_band_label": scenario.error_band_label,
            "selected_count": scenario.selected_count,
            "risk_a_counts": scenario.risk_a_counts,
            "risk_b_counts": scenario.risk_b_counts,
            "risk_a_unstable": scenario.risk_a_unstable,
            "risk_b_unstable": scenario.risk_b_unstable,
            "baseline_mean": scenario.baseline_mean,
            "hypothetical_mean": scenario.hypothetical_mean,
        }
    return payload


class DeliveryError(RuntimeError):
    """Raised when the technical package cannot be built or verified."""


@dataclass(frozen=True)
class DeliveryManifest:
    archive: Path
    sha256: str
    size_bytes: int
    file_count: int
    manifest: dict = field(default_factory=dict)


FORBIDDEN_PARTS = {
    ".git",
    ".superpowers",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "build",
    "test-results",
    "playwright-report",
    "coverage",
    "cartas",
    "cartas_firmadas",
}
FORBIDDEN_NAME_FRAGMENTS = ("secret", "credential", "credencial", "password", "private_key")

ALLOWLIST_FILES = (
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "compose.yaml",
    ".env.example",
    ".dockerignore",
    "alembic.ini",
    "data/sources.json",
    "docs/api/openapi.json",
    "apps/web/package.json",
    "apps/web/package-lock.json",
    "apps/web/index.html",
    "apps/web/tsconfig.json",
    "apps/web/tsconfig.app.json",
    "apps/web/tsconfig.node.json",
    "apps/web/vite.config.ts",
    "apps/web/vitest.config.ts",
    "apps/web/playwright.config.ts",
    "apps/web/eslint.config.js",
)

ALLOWLIST_DIRS: tuple[tuple[str, frozenset[str]], ...] = (
    ("apps/api/participa_geo", frozenset({".py"})),
    ("apps/web/src", frozenset({".ts", ".tsx", ".css"})),
    ("apps/web/tests", frozenset({".ts"})),
    ("tests", frozenset({".py", ".ts"})),
    (".github/workflows", frozenset({".yml", ".yaml"})),
    ("pipelines", frozenset({".py"})),
    ("gis", frozenset({".py", ".sld"})),
    ("alembic", frozenset({".py", ".mako", ".ini"})),
    ("infrastructure", frozenset({".py", ".sh", ".conf", ".dockerfile"})),
    ("docs", frozenset({".md", ".ttf", ".txt"})),
    ("data/processed/model", frozenset({".json", ".csv", ".parquet"})),
)

ALLOWLIST_EXPLICIT = (
    "data/raw/ccpc/jalisco-2009.csv",
    "data/raw/ccpc/jalisco-2012.csv",
    "data/raw/ccpc/jalisco-2015.csv",
    "data/raw/ccpc/jalisco-2018.csv",
    "data/raw/ccpc/jalisco-2021.csv",
    "data/raw/ccpc/jalisco-2024.csv",
    "data/raw/gis/ine-jalisco-2025-12-15.zip",
    "data/processed/municipal-observations.parquet",
    "data/processed/quality.json",
    "data/processed/provenance.json",
    "data/processed/gis/reference-2025-12-15.geojson",
    "data/processed/gis/reference-2025-12-15.geojson.sha256",
    "data/sources-national.json",
    "docs/api/openapi.json",
    "data/processed/national/national-ingest.json",
    "data/processed/national/municipal-observations.csv",
    "data/processed/national/continuity/district-observations.csv",
    "data/processed/national/continuity/coverage-report.csv",
    "data/processed/national/continuity/bridge-municipality-district.csv",
    "data/processed/national/model/model.json",
    "data/processed/national/model/evaluation.json",
    "data/processed/national/model/manifest.json",
    "data/processed/national/model/predictions-2027.parquet",
    "data/processed/national/model/exclusions-by-cut.csv",
)

REQUIRED_MEMBERS = (
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "compose.yaml",
    ".env.example",
    ".dockerignore",
    "infrastructure/docker/api.Dockerfile",
    "infrastructure/docker/web.Dockerfile",
    "data/sources.json",
    "docs/api/openapi.json",
    "data/processed/municipal-observations.parquet",
    "data/processed/quality.json",
    "data/processed/provenance.json",
    "data/processed/model/model.json",
    "data/processed/model/evaluation.json",
    "data/processed/model/manifest.json",
    "data/processed/model/predictions-2027.parquet",
    "data/processed/model/exclusions-by-cut.csv",
    "data/processed/gis/reference-2025-12-15.geojson",
    "sources/SOURCES.md",
    "sources/sources.json",
    "dictionaries/history.csv",
    "dictionaries/scenario.csv",
    "docs/hackathon/delivery-checklist.md",
    "docs/hackathon/source-licenses.md",
    "reports/methodology.pdf",
    "reports/executive.pdf",
)

REQUIRED_NATIONAL_MEMBERS = (
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "compose.yaml",
    ".env.example",
    ".dockerignore",
    "infrastructure/docker/api.Dockerfile",
    "infrastructure/docker/web.Dockerfile",
    "data/sources-national.json",
    "data/processed/national/national-ingest.json",
    "data/processed/national/municipal-observations.csv",
    "data/processed/national/model/model.json",
    "data/processed/national/model/evaluation.json",
    "data/processed/national/model/manifest.json",
    "data/processed/national/model/predictions-2027.parquet",
    "data/processed/national/model/exclusions-by-cut.csv",
    "data/processed/national/continuity/district-observations.csv",
    "data/processed/national/continuity/coverage-report.csv",
    "data/processed/national/continuity/bridge-municipality-district.csv",
    "sources/SOURCES.md",
    "sources/sources.json",
    "dictionaries/history.csv",
    "dictionaries/scenario.csv",
    "docs/hackathon/delivery-checklist.md",
    "docs/hackathon/source-licenses.md",
    "reports/methodology.pdf",
    "reports/executive.pdf",
    "reports/district-observations.csv",
)

RAW_SOURCE_MEMBERS = (
    "data/raw/ccpc/jalisco-2009.csv",
    "data/raw/ccpc/jalisco-2012.csv",
    "data/raw/ccpc/jalisco-2015.csv",
    "data/raw/ccpc/jalisco-2018.csv",
    "data/raw/ccpc/jalisco-2021.csv",
    "data/raw/ccpc/jalisco-2024.csv",
    "data/raw/gis/ine-jalisco-2025-12-15.zip",
)
NATIONAL_RAW_SOURCE_MEMBERS = tuple(
    [f"data/raw/ccpc-national/ccpc-{year}.zip" for year in (2009, 2012, 2015, 2018, 2021, 2024)]
    + [f"data/raw/gis/national/{state_code:02d}.zip" for state_code in range(1, 33)]
)

SCENARIO_REPORT_MEMBERS = (
    "reports/scenario.csv",
    "reports/scenario.geojson",
    "reports/scenario.pdf",
    "reports/scenario-map.png",
    "reports/scenario-map.pdf",
)


def _is_forbidden(relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts}
    if parts & FORBIDDEN_PARTS:
        return True
    name = relative.name.lower()
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    return any(fragment in name for fragment in FORBIDDEN_NAME_FRAGMENTS)


def _candidate_files(
    root: Path, *, include_raw_sources: bool, national: bool = False
) -> list[Path]:
    candidates: list[Path] = []
    allowed_explicit = set(ALLOWLIST_EXPLICIT) | set(ALLOWLIST_FILES)
    allowed_explicit.update(NATIONAL_RAW_SOURCE_MEMBERS if include_raw_sources else ())
    if national:
        allowed_explicit = {
            item
            for item in allowed_explicit
            if not item.startswith("data/raw/ccpc/")
            and item != "data/raw/gis/ine-jalisco-2025-12-15.zip"
            and item != "data/sources.json"
        }
    if not include_raw_sources:
        allowed_explicit = {item for item in allowed_explicit if not item.startswith("data/raw/")}
    for relative in allowed_explicit:
        path = root / relative
        if path.is_file():
            candidates.append(path)
    for directory, suffixes in ALLOWLIST_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                candidates.append(path)
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if _is_forbidden(relative):
            continue
        seen.add(resolved)
        unique.append(path)
    return sorted(unique, key=lambda item: item.relative_to(root).as_posix())


def _zip_info(arcname: str, mode: int) -> zipfile.ZipInfo:
    """A deterministic ZIP entry that preserves the Unix file mode."""
    info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | mode) << 16
    return info


def _add_bytes(
    archive: zipfile.ZipFile,
    arcname: str,
    payload: bytes,
    files: dict[str, dict[str, Any]],
) -> None:
    digest = hashlib.sha256(payload).hexdigest()
    archive.writestr(_zip_info(arcname, 0o644), payload)
    files[arcname] = {"sha256": digest, "bytes": len(payload)}


def _add_path(
    archive: zipfile.ZipFile,
    arcname: str,
    path: Path,
    files: dict[str, dict[str, Any]],
) -> None:
    digest = hashlib.sha256()
    size = 0
    mode = path.stat().st_mode & 0o777
    with path.open("rb") as source, archive.open(_zip_info(arcname, mode or 0o644), "w") as target:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            target.write(chunk)
    files[arcname] = {"sha256": digest.hexdigest(), "bytes": size}


def _sources_markdown(context: DeliveryContext, *, include_raw_sources: bool) -> bytes:
    mode = (
        "confirmado: se incluyen los CSV/ZIP originales con atribución"
        if include_raw_sources
        else "sólo checksums/URL: no se incluyen los originales"
    )
    lines = [
        "# Fuentes CCPC y checksums",
        "",
        f"Modo de entrega: **{mode}**.",
        "",
        "La API y las exportaciones analíticas sólo exponen agregados municipales.",
        "Los originales, cuando se incluyen, conservan la granularidad pública del INE",
        "(sección × sexo × edad) y no contienen listas nominales ni identificadores",
        "individuales. Está prohibida cualquier inferencia personal.",
        "",
        "| Año | URL | Miembro | SHA-256 |",
        "|---|---|---|---|",
    ]
    for source in context.sources:
        lines.append(
            f"| {source.year} | {source.source_url} | {source.member} | `{source.sha256}` |"
        )
    lines.extend(
        [
            "",
            "## Condiciones de redistribución",
            "",
            _license_review_text(),
            "",
            "Si no se confirma la licencia, use el modo `--skip-sources` y descargue",
            "los originales desde las URL/checksums anteriores.",
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _sources_json(context: DeliveryContext, *, include_raw_sources: bool) -> bytes:
    payload = {
        "source_mode": "confirm" if include_raw_sources else "skip",
        "raw_sources_included": include_raw_sources,
        "license_review": _license_review_text(),
        "sources": [
            {
                "year": source.year,
                "source_url": source.source_url,
                "member": source.member,
                "sha256": source.sha256,
                "municipality_count": source.municipality_count,
                "ln": source.ln,
            }
            for source in context.sources
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _license_review_text() -> str:
    return (
        "Fuentes INE CCPC: se conservan URL, miembro, corte y checksum. La página "
        "pública del INE no publica una licencia de redistribución explícita; el "
        "usuario debe confirmar las condiciones antes de una publicación abierta. "
        "Si no las confirma, sustituya los CSV/ZIP originales por checksums e "
        "instrucciones de descarga. Ver docs/hackathon/source-licenses.md."
    )


def build_technical_zip(
    context: DeliveryContext,
    output: Path | str,
    *,
    root: Path | str | None = None,
    reports: dict[str, Path | str | bytes] | None = None,
    strict: bool = True,
    team_slug: str | None = None,
    include_raw_sources: bool = False,
) -> DeliveryManifest:
    """Build and atomically publish the allowlisted technical ZIP.

    ``include_raw_sources`` is only true after an explicit human confirmation
    (CLI ``--confirm-source-license``). The default (and ``--skip-sources``)
    omits the original CSVs/GIS ZIP and ships ``sources/SOURCES.md`` +
    ``sources/sources.json`` with URLs and SHA-256 values instead.
    """
    source_root = Path(root) if root is not None else repo_root()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".tmp-{uuid4().hex}.zip"

    required = list(REQUIRED_NATIONAL_MEMBERS if context.national else REQUIRED_MEMBERS)
    if include_raw_sources:
        required.extend(NATIONAL_RAW_SOURCE_MEMBERS if context.national else RAW_SOURCE_MEMBERS)
    if context.scenario is not None:
        required.extend(SCENARIO_REPORT_MEMBERS)
    required = list(dict.fromkeys(required))

    files: dict[str, dict[str, Any]] = {}
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for path in _candidate_files(
                source_root,
                include_raw_sources=include_raw_sources,
                national=context.national,
            ):
                relative = path.relative_to(source_root).as_posix()
                _add_path(archive, relative, path, files)

            _add_bytes(
                archive,
                "dictionaries/history.csv",
                history_dictionary_csv(),
                files,
            )
            _add_bytes(
                archive,
                "dictionaries/scenario.csv",
                scenario_dictionary_csv(),
                files,
            )
            _add_bytes(
                archive,
                "sources/SOURCES.md",
                _sources_markdown(context, include_raw_sources=include_raw_sources),
                files,
            )
            _add_bytes(
                archive,
                "sources/sources.json",
                _sources_json(context, include_raw_sources=include_raw_sources),
                files,
            )

            for arcname, value in (reports or {}).items():
                safe = Path(arcname).as_posix().lstrip("/")
                if ".." in Path(safe).parts or _is_forbidden(Path(safe)):
                    raise DeliveryError(f"ruta de reporte no permitida: {arcname}")
                if isinstance(value, (bytes, bytearray)):
                    _add_bytes(archive, safe, bytes(value), files)
                else:
                    path = Path(value)
                    if not path.is_file():
                        raise DeliveryError(f"reporte faltante: {path}")
                    _add_path(archive, safe, path, files)

            missing = [member for member in required if member not in files]
            if strict and missing:
                raise DeliveryError(
                    "faltan archivos obligatorios en el paquete: " + ", ".join(missing)
                )

            manifest = {
                "manifest_version": "1.0",
                "team_slug": team_slug or context.team_slug,
                "eje": context.eje,
                "generated_at": context.generated_at.isoformat(),
                "reference_date": context.reference_date,
                "data_aggregate_sha256": context.data_aggregate_sha256,
                "dataset_version_ids": [str(item) for item in context.dataset_version_ids],
                "source_mode": "confirm" if include_raw_sources else "skip",
                "raw_sources_included": include_raw_sources,
                "source_license_confirmed": include_raw_sources,
                "scenario_required": context.scenario is not None,
                "national": context.national,
                "scenario_id": (str(context.scenario.scenario_id) if context.scenario else None),
                "complete": bool(strict and not missing),
                "missing": missing,
                "model": context_manifest(context)["model"],
                "cohort": context_manifest(context)["cohort"],
                "scenario": context_manifest(context).get("scenario"),
                "sources": context_manifest(context)["sources"],
                "assumptions": (context.scenario.rationale_text if context.scenario else None),
                "error_band_label": (
                    context.scenario.error_band_label if context.scenario else None
                ),
                "license_review": _license_review_text(),
                "required_members": required,
                "not_included": [
                    ".git",
                    "node_modules",
                    "caches",
                    ".env",
                    "cartas firmadas / contactos",
                    "secretos",
                    "datos personales",
                ],
                "files": files,
            }
            manifest_payload = (
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            _add_bytes(archive, "MANIFEST.json", manifest_payload, files)

            checksum_lines = "".join(
                f"{entry['sha256']}  {name}\n"
                for name, entry in sorted(files.items())
                if name != "CHECKSUMS.sha256"
            )
            _add_bytes(
                archive,
                "CHECKSUMS.sha256",
                checksum_lines.encode("utf-8"),
                files,
            )
        os.replace(temporary, output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    digest = hashlib.sha256()
    with output.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return DeliveryManifest(
        archive=output,
        sha256=digest.hexdigest(),
        size_bytes=output.stat().st_size,
        file_count=len(files),
        manifest=manifest,
    )


def _parse_checksums(payload: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in payload.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise DeliveryError("línea de checksum inválida")
        checksums[parts[1]] = parts[0]
    return checksums


def verify_archive(archive_path: Path | str) -> dict:
    """Verify names, manifest, required files and every SHA-256 checksum."""
    path = Path(archive_path)
    if not path.is_file():
        raise DeliveryError(f"archivo inexistente: {path}")
    errors: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            duplicates = {name for name in names if names.count(name) > 1}
            if duplicates:
                errors.append(f"miembros duplicados: {sorted(duplicates)}")
            for name in names:
                if _is_forbidden(Path(name)):
                    errors.append(f"miembro prohibido: {name}")
            if "MANIFEST.json" not in names:
                raise DeliveryError("el paquete no contiene MANIFEST.json")
            manifest = json.loads(archive.read("MANIFEST.json"))
            files = manifest.get("files") or {}
            if not isinstance(files, dict):
                raise DeliveryError("MANIFEST.json no contiene el mapa de archivos")
            for name in names:
                if name in {"MANIFEST.json", "CHECKSUMS.sha256"}:
                    continue
                if name not in files:
                    errors.append(f"archivo no declarado: {name}")
                    continue
                payload = archive.read(name)
                digest = hashlib.sha256(payload).hexdigest()
                if digest != files[name].get("sha256"):
                    errors.append(f"hash no coincide: {name}")
                if len(payload) != int(files[name].get("bytes", -1)):
                    errors.append(f"tamaño no coincide: {name}")
            for name in files:
                if name not in names:
                    errors.append(f"archivo declarado ausente: {name}")
            if "CHECKSUMS.sha256" in names:
                checksums = _parse_checksums(archive.read("CHECKSUMS.sha256").decode("utf-8"))
                for name, expected in checksums.items():
                    if name not in names:
                        errors.append(f"checksum de archivo ausente: {name}")
                    elif hashlib.sha256(archive.read(name)).hexdigest() != expected:
                        errors.append(f"checksum no coincide: {name}")

            source_mode = str(manifest.get("source_mode", "confirm"))
            raw_names = [
                name
                for name in names
                if name.startswith("data/raw/ccpc/")
                or name.startswith("data/raw/ccpc-national/")
                or name.startswith("data/raw/gis/")
            ]
            if source_mode == "skip":
                if raw_names:
                    errors.append(
                        "el modo skip-sources no debe incluir originales: "
                        + ", ".join(raw_names[:5])
                    )
                for member in ("sources/SOURCES.md", "sources/sources.json"):
                    if member not in names:
                        errors.append(f"falta el archivo de fuentes: {member}")
            else:
                source_members = (
                    NATIONAL_RAW_SOURCE_MEMBERS if manifest.get("national") else RAW_SOURCE_MEMBERS
                )
                for member in source_members:
                    if member not in names:
                        errors.append(f"falta el original confirmado: {member}")

            required = list(manifest.get("required_members") or REQUIRED_MEMBERS)
            if manifest.get("scenario_required"):
                required.extend(SCENARIO_REPORT_MEMBERS)
            if manifest.get("complete"):
                for member in dict.fromkeys(required):
                    if member not in names:
                        errors.append(f"falta el miembro obligatorio: {member}")
    except zipfile.BadZipFile as exc:
        raise DeliveryError("el archivo no es un ZIP válido") from exc

    if errors:
        raise DeliveryError("; ".join(errors[:20]))
    return {
        "archive": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
        "file_count": len(files),
        "complete": bool(manifest.get("complete")),
        "source_mode": manifest.get("source_mode"),
        "scenario_required": bool(manifest.get("scenario_required")),
        "team_slug": manifest.get("team_slug"),
        "generated_at": manifest.get("generated_at"),
        "members": names,
    }


__all__ = [
    "ALLOWLIST_DIRS",
    "ALLOWLIST_EXPLICIT",
    "ALLOWLIST_FILES",
    "CohortFacts",
    "DeliveryContext",
    "DeliveryError",
    "DeliveryManifest",
    "FORBIDDEN_PARTS",
    "ModelFacts",
    "NATIONAL_RAW_SOURCE_MEMBERS",
    "RAW_SOURCE_MEMBERS",
    "REQUIRED_NATIONAL_MEMBERS",
    "REQUIRED_MEMBERS",
    "SCENARIO_REPORT_MEMBERS",
    "ScenarioFacts",
    "SourceFact",
    "build_technical_zip",
    "context_manifest",
    "load_delivery_context",
    "repo_root",
    "verify_archive",
]
