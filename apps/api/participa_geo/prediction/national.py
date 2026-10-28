"""National municipal cohort construction and temporal model training."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from participa_geo.indicators.calculations import assess_quality
from participa_geo.ingestion.schema import (
    FootprintStatus,
    IdentityStatus,
    MunicipalObservation,
)
from participa_geo.prediction.artifacts import compute_model_run_id
from participa_geo.prediction.cohorts import TARGET_YEAR, TerritoryIdentity
from participa_geo.prediction.evaluation import ModelMetrics, compute_metrics
from participa_geo.prediction.features import FEATURE_ORDER, abstention_pct, is_midterm_election
from participa_geo.prediction.risk import (
    classify_risk,
    empirical_coverage,
    error_band_amplitude,
    risk_band,
)
from participa_geo.territory import TerritoryKey, territory_id

ALPHA = 1.0
REQUIRED_CUTS = (2015, 2018, 2021, 2024, 2027)
FIXED_EFFECT_STATES = tuple(f"{state:02d}" for state in range(2, 33))


@dataclass(frozen=True)
class NationalCohortRow:
    state_code: str
    municipality_code: str
    municipality_name: str
    target_year: int
    target: float | None
    target_known_count: int
    features: dict[str, float]
    origins: dict[str, int | None]


@dataclass(frozen=True)
class NationalCohort:
    target_year: int
    rows: tuple[NationalCohortRow, ...]
    exclusions: tuple[NationalExclusion, ...]


@dataclass(frozen=True)
class NationalExclusion:
    state_code: str
    municipality_code: str
    municipality_name: str
    reasons: tuple[str, ...]
    identity_status: IdentityStatus | None
    footprint_status: FootprintStatus | None


@dataclass(frozen=True)
class NationalPrediction:
    state_code: str
    municipality_code: str
    municipality_name: str
    estimate: float | None
    lower: float | None
    upper: float | None
    risk: str
    eligible: bool
    reasons: tuple[str, ...]
    identity_status: str | None
    footprint_status: str | None
    model_run_id: UUID


@dataclass(frozen=True)
class NationalModelBundle:
    level: str
    model_run_id: UUID
    family: str
    predictions: tuple[NationalPrediction, ...]
    candidate_count: int
    total_count: int
    model_payload: dict
    evaluation_payload: dict


def _status(value) -> str:
    return str(getattr(value, "value", value))


def build_national_cohort(
    observations: Sequence[MunicipalObservation],
    target_year: int,
    identity_statuses: Mapping[tuple[str, str], TerritoryIdentity],
) -> NationalCohort:
    """Build one state-qualified cohort, failing on missing identity evidence."""
    if not identity_statuses:
        raise ValueError("national identity statuses are required; refusing to assume verified")
    rows_by_key_year = {
        (o.key.state_code, o.key.municipality_code, o.year): o for o in observations
    }
    names = {(o.key.state_code, o.key.municipality_code): o.municipality_name for o in observations}
    observed_keys = {(o.key.state_code, o.key.municipality_code) for o in observations}
    missing = observed_keys - set(identity_statuses)
    if missing:
        raise ValueError(
            f"missing national identity status for municipalities: {sorted(missing)[:10]}"
        )
    required_years = (
        (2021, 2024)
        if target_year == TARGET_YEAR
        else (target_year - 6, target_year - 3, target_year)
    )
    lag6, lag3 = target_year - 6, target_year - 3
    eligible: list[NationalCohortRow] = []
    excluded: list[NationalExclusion] = []
    for state, code in sorted(identity_statuses):
        ident = identity_statuses[(state, code)]
        reasons: list[str] = []
        if _status(ident.identity_status) != IdentityStatus.verified_catalogue.value:
            reasons.append(
                "ambiguous_identity"
                if _status(ident.identity_status) == "ambiguous"
                else "known_administrative_change"
            )
        if _status(ident.footprint_status) == FootprintStatus.known_changed.value:
            reasons.append("known_administrative_change")
        for year in required_years:
            obs = rows_by_key_year.get((state, code, year))
            if obs is None:
                reasons.append("missing_lag")
            else:
                reasons.extend(assess_quality(obs).reasons)
        features: dict[str, float] = {}
        same = rows_by_key_year.get((state, code, lag6))
        previous = rows_by_key_year.get((state, code, lag3))
        target = rows_by_key_year.get((state, code, target_year))
        if same is not None and previous is not None:
            abstention_same = abstention_pct(same)
            abstention_prev = abstention_pct(previous)
            shares = (previous.young_share, previous.senior_share, previous.rural_share)
            if abstention_same is None or abstention_prev is None or any(v is None for v in shares):
                reasons.append("missing_feature")
            else:
                features = {
                    "same_type_abstention_pct": abstention_same,
                    "previous_abstention_pct": abstention_prev,
                    "previous_young_share": float(shares[0]),
                    "previous_senior_share": float(shares[1]),
                    "previous_rural_share": float(shares[2]),
                    "is_midterm": float(is_midterm_election(target_year)),
                }
        reasons = list(dict.fromkeys(reasons))
        name = names.get((state, code), code)
        if reasons:
            excluded.append(
                NationalExclusion(
                    state, code, name, tuple(reasons), ident.identity_status, ident.footprint_status
                )
            )
        else:
            eligible.append(
                NationalCohortRow(
                    state,
                    code,
                    name,
                    target_year,
                    abstention_pct(target) if target is not None else None,
                    target.sv + target.nv if target is not None else 0,
                    features,
                    {
                        "same_type_abstention_pct": lag6,
                        "previous_abstention_pct": lag3,
                        "previous_young_share": lag3,
                        "previous_senior_share": lag3,
                        "previous_rural_share": lag3,
                        "is_midterm": None,
                    },
                )
            )
    return NationalCohort(target_year, tuple(eligible), tuple(excluded))


def _matrix(rows: Sequence[NationalCohortRow], states: Sequence[str]) -> np.ndarray:
    base = [[r.features[name] for name in FEATURE_ORDER] for r in rows]
    effects = [[float(r.state_code == state) for state in states] for r in rows]
    return np.asarray([a + b for a, b in zip(base, effects, strict=True)], dtype=np.float64)


@dataclass(frozen=True)
class _Fit:
    intercept: float
    coefficients: tuple[float, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    states: tuple[str, ...]


def _fit(datasets: Sequence[NationalCohort], states: Sequence[str]) -> _Fit:
    rows = [row for ds in datasets for row in ds.rows]
    X = _matrix(rows, states)
    y = np.asarray([row.target for row in rows], dtype=np.float64)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(X)
    model = Ridge(alpha=ALPHA)
    model.fit(scaled, y)
    return _Fit(
        float(model.intercept_),
        tuple(map(float, model.coef_)),
        tuple(map(float, scaler.mean_)),
        tuple(map(float, scaler.scale_)),
        tuple(states),
    )


def _predict(fit: _Fit, dataset: NationalCohort) -> tuple[np.ndarray, np.ndarray]:
    X = _matrix(dataset.rows, fit.states)
    raw = fit.intercept + ((X - fit.mean) / fit.scale) @ np.asarray(fit.coefficients)
    return raw, np.clip(raw, 0, 100)


def _metrics(dataset: NationalCohort, prediction: np.ndarray) -> ModelMetrics:
    return compute_metrics(
        [r.target for r in dataset.rows],
        prediction,
        [r.target_known_count for r in dataset.rows],
    )


def _state_metrics(dataset: NationalCohort, prediction: np.ndarray) -> dict[str, dict]:
    """Compute unweighted evaluation metrics for each represented state."""
    result = {}
    for state in sorted({row.state_code for row in dataset.rows}):
        indexes = [i for i, row in enumerate(dataset.rows) if row.state_code == state]
        actual = np.asarray([dataset.rows[i].target for i in indexes], dtype=np.float64)
        errors = prediction[indexes] - actual
        result[state] = {
            "mae": float(np.mean(np.abs(errors))),
            "rmse": float(np.sqrt(np.mean(np.square(errors)))),
            "bias": float(np.mean(errors)),
            "n": len(indexes),
        }
    return result


def train_national(
    observations: Sequence[MunicipalObservation],
    level: str = "municipality",
    output_dir: Path | None = None,
    *,
    identity_statuses: Mapping[tuple[str, str], TerritoryIdentity] | None = None,
    universe: Sequence[tuple[str, str]] | None = None,
) -> NationalModelBundle:
    """Select/evaluate and fit the national municipal model for 2027."""
    if level != "municipality":
        raise ValueError("Task 5 trains municipality only; district model is unavailable")
    if identity_statuses is None:
        raise ValueError("national identity statuses are required")
    observations = list(observations)
    datasets = {
        year: build_national_cohort(observations, year, identity_statuses) for year in REQUIRED_CUTS
    }
    if not all(datasets[y].rows for y in (2015, 2018, 2021, 2024)):
        raise ValueError("national temporal training cohort is empty")
    states = FIXED_EFFECT_STATES
    fit_train = _fit([datasets[2015], datasets[2018]], states)
    val = datasets[2021]
    _, pred_m1_val = _predict(fit_train, val)
    pred_m0_val = np.array([r.features["same_type_abstention_pct"] for r in val.rows])
    m0_2021, m1_2021 = _metrics(val, pred_m0_val), _metrics(val, pred_m1_val)
    family = "M1" if m1_2021.mae < m0_2021.mae else "M0"

    test = datasets[2024]
    pred_m0_2024 = np.array([r.features["same_type_abstention_pct"] for r in test.rows])
    fit_test = _fit([datasets[2015], datasets[2018], datasets[2021]], states)
    _, pred_m1_2024 = _predict(fit_test, test)
    m0_2024, m1_2024 = _metrics(test, pred_m0_2024), _metrics(test, pred_m1_2024)
    selected_errors = (
        pred_m1_val - np.array([r.target for r in val.rows])
        if family == "M1"
        else pred_m0_val - np.array([r.target for r in val.rows])
    )
    band = error_band_amplitude(selected_errors)

    final_train = [datasets[y] for y in (2015, 2018, 2021, 2024)]
    final_fit = _fit(final_train, states)
    forecast = datasets[2027]
    _, pred_m1 = _predict(final_fit, forecast)
    pred_m0 = np.array([r.features["same_type_abstention_pct"] for r in forecast.rows])

    data = hashlib.sha256(
        json.dumps(
            [
                [
                    o.key.state_code,
                    o.key.municipality_code,
                    o.year,
                    o.ln,
                    o.sv,
                    o.nv,
                    o.ns,
                    o.young_share,
                    o.senior_share,
                    o.rural_share,
                ]
                for o in sorted(
                    observations, key=lambda o: (o.key.state_code, o.key.municipality_code, o.year)
                )
            ],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    selected = {
        "family": family,
        "data": data,
        "level": level,
        "feature_order": list(FEATURE_ORDER),
        "fixed_effect_states": list(states),
        "alpha": ALPHA,
        "identity": [
            (s, c, _status(i.identity_status), _status(i.footprint_status))
            for (s, c), i in sorted(identity_statuses.items())
        ],
        "cohorts": {
            str(y): [(r.state_code, r.municipality_code) for r in datasets[y].rows]
            for y in REQUIRED_CUTS
        },
        "exclusions": {
            str(y): [(e.state_code, e.municipality_code, e.reasons) for e in datasets[y].exclusions]
            for y in REQUIRED_CUTS
        },
        "metrics": {
            "m0_2021": m0_2021.__dict__,
            "m1_2021": m1_2021.__dict__,
            "m0_2024": m0_2024.__dict__,
            "m1_2024": m1_2024.__dict__,
        },
        "m0": {"definition": "same municipal territory/type at t-6"},
        "candidate_m1_2021": {
            "intercept": fit_train.intercept,
            "coefficients": list(fit_train.coefficients),
            "scaler": {"mean": list(fit_train.mean), "scale": list(fit_train.scale)},
            "metrics": m1_2021.__dict__,
        },
        "candidate_m1_2024": {
            "intercept": fit_test.intercept,
            "coefficients": list(fit_test.coefficients),
            "scaler": {"mean": list(fit_test.mean), "scale": list(fit_test.scale)},
            "metrics": m1_2024.__dict__,
        },
        "band": band,
        "final_fit": {
            "intercept": final_fit.intercept,
            "coefficients": final_fit.coefficients,
            "mean": final_fit.mean,
            "scale": final_fit.scale,
        },
    }
    run_id = compute_model_run_id(selected)
    final_prediction = pred_m1 if family == "M1" else pred_m0
    by_key = {(r.state_code, r.municipality_code): i for i, r in enumerate(forecast.rows)}
    obs_names = {
        (o.key.state_code, o.key.municipality_code): o.municipality_name for o in observations
    }
    universe_keys = sorted(set(universe if universe is not None else identity_statuses))
    exclusions = {(e.state_code, e.municipality_code): e for e in datasets[2027].exclusions}
    records: list[NationalPrediction] = []
    for key in universe_keys:
        idx = by_key.get(key)
        ident = identity_statuses.get(key)
        if idx is None:
            exclusion = exclusions.get(key)
            reasons = exclusion.reasons if exclusion else ("missing_lag",)
            records.append(
                NationalPrediction(
                    *key,
                    obs_names.get(key, key[1]),
                    None,
                    None,
                    None,
                    "insufficient",
                    False,
                    tuple(reasons),
                    _status(ident.identity_status) if ident else None,
                    _status(ident.footprint_status) if ident else None,
                    run_id,
                )
            )
        else:
            estimate = float(final_prediction[idx])
            low, high = risk_band(estimate, band)
            records.append(
                NationalPrediction(
                    *key,
                    forecast.rows[idx].municipality_name,
                    estimate,
                    low,
                    high,
                    classify_risk(estimate, True),
                    True,
                    (),
                    _status(ident.identity_status),
                    _status(ident.footprint_status),
                    run_id,
                )
            )
    evaluation = {
        "level": level,
        "selected_family": family,
        "validation_year": 2021,
        "test_year": 2024,
        "selection": {"m0_mae_2021": m0_2021.mae, "m1_mae_2021": m1_2021.mae},
        "metrics": {
            "m0": {"2021": m0_2021.__dict__, "2024": m0_2024.__dict__},
            "m1": {"2021": m1_2021.__dict__, "2024": m1_2024.__dict__},
        },
        "state_metrics": {
            "m0": {
                "2021": _state_metrics(val, pred_m0_val),
                "2024": _state_metrics(test, pred_m0_2024),
            },
            "m1": {
                "2021": _state_metrics(val, pred_m1_val),
                "2024": _state_metrics(test, pred_m1_2024),
            },
        },
        "band": {
            "amplitude_pp": band,
            "n_errors_2021": len(selected_errors),
            "empirical_coverage_2024": empirical_coverage(
                (pred_m1_2024 if family == "M1" else pred_m0_2024)
                - np.array([r.target for r in test.rows]),
                band,
            ),
        },
        "cohorts": {
            str(y): {
                "eligible_count": len(datasets[y].rows),
                "excluded_count": len(datasets[y].exclusions),
            }
            for y in REQUIRED_CUTS
        },
        "data_aggregate_sha256": data,
    }
    model_payload = {
        "level": level,
        "target_year": TARGET_YEAR,
        "model_run_id": str(run_id),
        "family": family,
        "alpha": ALPHA,
        "feature_order": list(FEATURE_ORDER),
        "fixed_effect_states": list(states),
        "reference_state": "01",
        "intercept": final_fit.intercept,
        "coefficients": list(final_fit.coefficients),
        "scaler": {"mean": list(final_fit.mean), "scale": list(final_fit.scale)},
        "data_aggregate_sha256": data,
        "candidate_m1_2021": {
            "intercept": fit_train.intercept,
            "coefficients": list(fit_train.coefficients),
            "scaler": {"mean": list(fit_train.mean), "scale": list(fit_train.scale)},
            "metrics": m1_2021.__dict__,
        },
        "candidate_m1_2024": {
            "intercept": fit_test.intercept,
            "coefficients": list(fit_test.coefficients),
            "scaler": {"mean": list(fit_test.mean), "scale": list(fit_test.scale)},
            "metrics": m1_2024.__dict__,
        },
        "identity_sha256": hashlib.sha256(
            json.dumps(selected["identity"], sort_keys=True).encode()
        ).hexdigest(),
    }
    bundle = NationalModelBundle(
        level,
        run_id,
        family,
        tuple(records),
        len(forecast.rows),
        len(records),
        model_payload,
        evaluation,
    )
    if output_dir is not None:
        write_national_artifacts(bundle, datasets, data, selected, output_dir)
    return bundle


def write_national_artifacts(
    bundle: NationalModelBundle,
    datasets: Mapping[int, NationalCohort],
    data_hash: str,
    identity: dict,
    output_dir: Path,
) -> None:
    """Write deterministic JSON/Parquet/CSV artifacts without pickle/joblib."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _atomic_json(output / "model.json", bundle.model_payload)
    _atomic_json(output / "evaluation.json", bundle.evaluation_payload)
    frame = pd.DataFrame(
        [
            {
                "state_code": p.state_code,
                "municipality_code": p.municipality_code,
                "municipality_name": p.municipality_name,
                "target_year": TARGET_YEAR,
                "estimated_abstention_pct": p.estimate,
                "historical_error_lower_pct": p.lower,
                "historical_error_upper_pct": p.upper,
                "risk": p.risk,
                "eligible": p.eligible,
                "quality_reasons": ";".join(p.reasons),
                "identity_status": p.identity_status,
                "footprint_status": p.footprint_status,
                "territory_id": str(
                    territory_id(TerritoryKey("municipality", p.state_code, p.municipality_code))
                ),
                "model_run_id": str(p.model_run_id),
            }
            for p in bundle.predictions
        ]
    )
    _atomic_file(output / "predictions-2027.parquet", lambda p: frame.to_parquet(p, index=False))
    with (output / "exclusions-by-cut.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "state_code", "municipality_code", "reasons"])
        for year, dataset in sorted(datasets.items()):
            for exclusion in dataset.exclusions:
                writer.writerow(
                    [
                        year,
                        exclusion.state_code,
                        exclusion.municipality_code,
                        ";".join(exclusion.reasons),
                    ]
                )
    manifest = {
        "level": bundle.level,
        "model_run_id": str(bundle.model_run_id),
        "data_aggregate_sha256": data_hash,
        "identity": identity,
        "artifacts": {},
    }
    for name in (
        "model.json",
        "evaluation.json",
        "predictions-2027.parquet",
        "exclusions-by-cut.csv",
    ):
        content = (output / name).read_bytes()
        manifest["artifacts"][name] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
    _atomic_json(output / "manifest.json", manifest)


def _atomic_json(path: Path, value: dict) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True, default=str) + "\n").encode()
    _atomic_file(path, lambda temp: temp.write_bytes(payload))


def _atomic_file(path: Path, writer) -> None:
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    os.close(fd)
    temp = Path(name)
    try:
        writer(temp)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


__all__ = ["NationalCohort", "NationalModelBundle", "build_national_cohort", "train_national"]
