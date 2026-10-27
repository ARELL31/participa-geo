"""Deterministic, interpretable model training and temporal validation.

Temporal scheme (Spec §7, controller ruling #5):

- Fit/evaluate M0 and M1 on targets 2015/2018, validate on 2021. M1 is chosen
  only if it strictly reduces MAE on 2021; a tie keeps M0.
- Freeze the family, then evaluate 2024 (both models are still published, but
  2024 can never change the family, variables, alpha or thresholds).
- Final fit on 2015/2018/2021/2024 for the 2027 forecast.

M1 is ``StandardScaler`` + ``Ridge(alpha=1.0)`` on the six fixed features; the
scaler is fit on training rows only. Outputs are clipped to 0-100 and the clip
frequency is recorded. M0 is the same-municipality same-type abstention at t-6.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from participa_geo.indicators.calculations import QualityDecision
from participa_geo.ingestion.schema import MunicipalObservation, territory_id
from participa_geo.prediction.artifacts import (
    ModelBundle,
    PredictionRecord,
    compute_model_run_id,
    write_artifacts,
)
from participa_geo.prediction.cohorts import TARGET_YEAR
from participa_geo.prediction.evaluation import ModelMetrics, compute_metrics
from participa_geo.prediction.features import (
    FEATURE_ORDER,
    FeatureDataset,
    build_examples,
)
from participa_geo.prediction.risk import (
    classify_risk,
    empirical_coverage,
    error_band_amplitude,
    is_risk_unstable,
    risk_band,
)

#: Ridge regularization (fixed, never searched).
ALPHA = 1.0

#: Exact temporal cuts (Spec §7).
FIT_YEARS_SELECTION = (2015, 2018)
VALIDATION_YEAR = 2021
TEST_YEAR = 2024
FINAL_FIT_YEARS = (2015, 2018, 2021, 2024)


@dataclass(frozen=True)
class FittedRidge:
    """Serializable Ridge model: intercept, coefficients and scaler parameters."""

    intercept: float
    coefficients: tuple[float, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    feature_order: tuple[str, ...] = FEATURE_ORDER


@dataclass(frozen=True)
class EvaluationBundle:
    """Result of evaluating M0 vs M1 on a validation year."""

    validation_year: int
    m0: ModelMetrics
    m1: ModelMetrics
    selected_family: str
    m0_errors: tuple[float, ...]
    m1_errors: tuple[float, ...]
    fitted_m1: FittedRidge


def _feature_matrix(datasets: Sequence[FeatureDataset]) -> np.ndarray:
    return np.array(
        [
            [row.features[f] for f in FEATURE_ORDER]
            for ds in datasets
            for row in ds.rows
        ],
        dtype=np.float64,
    )


def _targets(datasets: Sequence[FeatureDataset]) -> np.ndarray:
    return np.array(
        [row.target for ds in datasets for row in ds.rows], dtype=np.float64
    )


def _weights(dataset: FeatureDataset) -> np.ndarray:
    return np.array([row.target_known_count for row in dataset.rows], dtype=np.float64)


def fit_ridge(datasets: Sequence[FeatureDataset], alpha: float = ALPHA) -> FittedRidge:
    """Fit StandardScaler + Ridge on the concatenated training rows only."""
    X = _feature_matrix(datasets)
    y = _targets(datasets)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = Ridge(alpha=alpha, random_state=0)
    model.fit(X_scaled, y)
    return FittedRidge(
        intercept=float(model.intercept_),
        coefficients=tuple(float(c) for c in model.coef_),
        scaler_mean=tuple(float(m) for m in scaler.mean_),
        scaler_scale=tuple(float(s) for s in scaler.scale_),
        feature_order=FEATURE_ORDER,
    )


def predict_ridge(
    fitted: FittedRidge, dataset: FeatureDataset
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(raw, clipped)`` predictions for one dataset."""
    X = _feature_matrix([dataset])
    mean = np.asarray(fitted.scaler_mean, dtype=np.float64)
    scale = np.asarray(fitted.scaler_scale, dtype=np.float64)
    coef = np.asarray(fitted.coefficients, dtype=np.float64)
    X_scaled = (X - mean) / scale
    raw = fitted.intercept + X_scaled @ coef
    clipped = np.clip(raw, 0.0, 100.0)
    return raw, clipped


def predict_m0(dataset: FeatureDataset) -> np.ndarray:
    """M0: the same-municipality same-type abstention at t-6."""
    return np.array(
        [row.features["same_type_abstention_pct"] for row in dataset.rows],
        dtype=np.float64,
    )


def select_family(m0_mae: float, m1_mae: float) -> str:
    """Choose M1 only on a strict MAE improvement; a tie keeps M0."""
    return "M1" if m1_mae < m0_mae else "M0"


def evaluate_models(
    fit_datasets: Sequence[FeatureDataset], validation_dataset: FeatureDataset
) -> EvaluationBundle:
    """Fit M1 on ``fit_datasets`` and compare M0 vs M1 on the validation year."""
    fitted_m1 = fit_ridge(fit_datasets)
    y_true = _targets([validation_dataset])
    weights = _weights(validation_dataset)

    pred_m0 = predict_m0(validation_dataset)
    raw_m1, pred_m1 = predict_ridge(fitted_m1, validation_dataset)
    clip_count = int(np.count_nonzero(raw_m1 != pred_m1))

    m0 = compute_metrics(y_true, pred_m0, weights, clipped_count=0)
    m1 = compute_metrics(y_true, pred_m1, weights, clipped_count=clip_count)
    selected = select_family(m0.mae, m1.mae)

    return EvaluationBundle(
        validation_year=validation_dataset.target_year,
        m0=m0,
        m1=m1,
        selected_family=selected,
        m0_errors=tuple(float(e) for e in (pred_m0 - y_true)),
        m1_errors=tuple(float(e) for e in (pred_m1 - y_true)),
        fitted_m1=fitted_m1,
    )


def _data_hash(observations: Sequence[MunicipalObservation]) -> str:
    items = [
        [
            obs.key.state_code,
            obs.key.municipality_code,
            obs.year,
            obs.ln,
            obs.sv,
            obs.nv,
            obs.ns,
            obs.young_share,
            obs.senior_share,
            obs.rural_share,
        ]
        for obs in sorted(observations, key=lambda o: (o.key.municipality_code, o.year))
    ]
    canonical = json.dumps(items, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _explanations(fitted: FittedRidge, dataset: FeatureDataset) -> list[dict]:
    """Additive explanation in the transformed scale (intercept + contributions)."""
    X = _feature_matrix([dataset])
    mean = np.asarray(fitted.scaler_mean, dtype=np.float64)
    scale = np.asarray(fitted.scaler_scale, dtype=np.float64)
    coef = np.asarray(fitted.coefficients, dtype=np.float64)
    Z = (X - mean) / scale
    contributions = Z * coef
    out: list[dict] = []
    for i, row in enumerate(dataset.rows):
        out.append(
            {
                "municipality_code": row.municipality_code,
                "intercept": float(fitted.intercept),
                "contributions": {
                    f: float(contributions[i, j]) for j, f in enumerate(FEATURE_ORDER)
                },
                "pre_clip_sum": float(fitted.intercept + contributions[i].sum()),
            }
        )
    return out


def _m0_explanations(dataset: FeatureDataset) -> list[dict]:
    """Additive explanation for M0: its single historical antecedent."""
    out: list[dict] = []
    for row in dataset.rows:
        contribution = row.features["same_type_abstention_pct"]
        out.append(
            {
                "municipality_code": row.municipality_code,
                "intercept": 0.0,
                "contributions": {"same_type_abstention_pct": contribution},
                "pre_clip_sum": contribution,
                "family": "M0",
            }
        )
    return out


def _fitted_identity(fitted: FittedRidge | None) -> dict | None:
    if fitted is None:
        return None
    return {
        "intercept": fitted.intercept,
        "coefficients": list(fitted.coefficients),
        "scaler_mean": list(fitted.scaler_mean),
        "scaler_scale": list(fitted.scaler_scale),
    }


def _metrics_identity(metrics: ModelMetrics) -> dict:
    return {
        "n": metrics.n,
        "mae": metrics.mae,
        "rmse": metrics.rmse,
        "bias": metrics.bias,
        "weighted_mae": metrics.weighted_mae,
        "clipped_count": metrics.clipped_count,
        "clipped_total": metrics.clipped_total,
    }


def _status_value(value: object) -> str | None:
    inner = getattr(value, "value", value)
    return str(inner) if inner is not None else None


def build_model_identity(
    *,
    family: str,
    data_hash: str,
    identity_statuses: Mapping[str, object],
    datasets: Mapping[int, FeatureDataset],
    selection: EvaluationBundle,
    m0_2024: ModelMetrics,
    m1_2024: ModelMetrics,
    amplitude: float | None,
    fitted_final: FittedRidge | None,
) -> dict:
    """Canonical content that determines ``model_run_id``.

    Besides the data hash and features, this hashes the identity-status map, the
    eligible cohort and exclusions for every cut, the candidate M1 parameters and
    both evaluations, and the final fitted parameters. Editing any of them minted
    a new model id instead of reusing an id with different outputs.
    """
    identity_rows = []
    for code in sorted(identity_statuses):
        ident = identity_statuses[code]
        identity_rows.append(
            {
                "municipality_code": code,
                "identity_status": _status_value(getattr(ident, "identity_status", None)),
                "footprint_status": _status_value(getattr(ident, "footprint_status", None)),
            }
        )

    cohorts: dict[str, dict] = {}
    for year in sorted(datasets):
        dataset = datasets[year]
        cohorts[str(year)] = {
            "eligible_codes": [row.municipality_code for row in dataset.rows],
            "exclusions": [
                {
                    "municipality_code": exclusion.municipality_code,
                    "reasons": list(exclusion.reasons),
                }
                for exclusion in dataset.exclusions
            ],
        }

    return {
        "schema": "participa-geo:model-identity:2",
        "family": family,
        "target_year": TARGET_YEAR,
        "data_sha256": data_hash,
        "feature_order": list(FEATURE_ORDER),
        "alpha": ALPHA,
        "validation_year": VALIDATION_YEAR,
        "test_year": TEST_YEAR,
        "identity_statuses": identity_rows,
        "cohorts": cohorts,
        "selection": {
            "m0_mae_2021": selection.m0.mae,
            "m1_mae_2021": selection.m1.mae,
        },
        "metrics": {
            "m0": {"2021": _metrics_identity(selection.m0), "2024": _metrics_identity(m0_2024)},
            "m1": {"2021": _metrics_identity(selection.m1), "2024": _metrics_identity(m1_2024)},
        },
        "band_amplitude_pp": amplitude,
        "final_model": _fitted_identity(fitted_final),
        "candidate_m1": _fitted_identity(selection.fitted_m1),
    }


def train_release(
    observations: Sequence[MunicipalObservation],
    output_dir: Path,
    *,
    identity_statuses: Mapping[str, object] | None = None,
) -> ModelBundle:
    """Run the full temporal scheme and write all artifacts atomically.

    ``identity_statuses`` is required (read from PostGIS by the caller); it is
    never assumed and a missing municipality raises loudly.
    """
    if identity_statuses is None:
        raise ValueError(
            "identity_statuses are required (read from PostGIS); refusing to assume "
            "verified identities"
        )

    observations = list(observations)
    data_hash = _data_hash(observations)

    datasets = {
        year: build_examples(observations, year, identity_statuses)
        for year in (2015, 2018, 2021, 2024, 2027)
    }

    # 1) Selection on 2021 only.
    selection = evaluate_models([datasets[2015], datasets[2018]], datasets[2021])
    family = selection.selected_family

    # 2) Freeze the family; evaluate 2024 (both models are still reported).
    y_2024 = _targets([datasets[2024]])
    w_2024 = _weights(datasets[2024])
    m0_2024 = compute_metrics(y_2024, predict_m0(datasets[2024]), w_2024)
    fitted_2024 = fit_ridge([datasets[2015], datasets[2018], datasets[2021]])
    raw_2024, pred_2024 = predict_ridge(fitted_2024, datasets[2024])
    m1_2024 = compute_metrics(
        y_2024, pred_2024, w_2024, clipped_count=int(np.count_nonzero(raw_2024 != pred_2024))
    )

    # 3) Final fit for 2027.
    if family == "M1":
        fitted_final = fit_ridge(
            [datasets[2015], datasets[2018], datasets[2021], datasets[2024]]
        )
        raw_final, pred_final = predict_ridge(fitted_final, datasets[2027])
    else:
        fitted_final = None
        pred_final = predict_m0(datasets[2027])
        raw_final = pred_final

    # 4) Uncertainty band: P90 absolute error of the selected family on 2021.
    errors_2021 = selection.m1_errors if family == "M1" else selection.m0_errors
    amplitude = error_band_amplitude(errors_2021)
    # Out-of-time empirical coverage: 2024 errors compared with the frozen 2021
    # band. This never changes the amplitude used for 2027.
    errors_2024 = (
        pred_2024 - y_2024
        if family == "M1"
        else predict_m0(datasets[2024]) - y_2024
    )

    # 5) Prediction records for every municipality (125), incl. insufficient.
    model_identity = build_model_identity(
        family=family,
        data_hash=data_hash,
        identity_statuses=identity_statuses,
        datasets=datasets,
        selection=selection,
        m0_2024=m0_2024,
        m1_2024=m1_2024,
        amplitude=amplitude,
        fitted_final=fitted_final,
    )
    model_run_id = compute_model_run_id(model_identity)

    eligible_by_code = {r.municipality_code: i for i, r in enumerate(datasets[2027].rows)}
    exclusion_by_code = {e.municipality_code: e for e in datasets[2027].exclusions}
    names = {obs.key.municipality_code: obs.municipality_name for obs in observations}
    universe = sorted(identity_statuses.keys())

    records: list[PredictionRecord] = []
    for code in universe:
        ident = identity_statuses[code]
        name = names.get(code, code)
        idx = eligible_by_code.get(code)
        if idx is not None:
            estimate = float(pred_final[idx])
            pre_clip = float(raw_final[idx])
            lower, upper = risk_band(estimate, amplitude)
            risk = classify_risk(estimate, True)
            unstable = is_risk_unstable(lower, upper)
            quality = QualityDecision(
                eligible=True,
                reasons=[],
                identity_status=getattr(ident, "identity_status", None),
                footprint_status=getattr(ident, "footprint_status", None),
            )
            records.append(
                PredictionRecord(
                    territory_id=territory_id("14", code),
                    municipality_code=code,
                    municipality_name=name,
                    target_year=TARGET_YEAR,
                    estimated_abstention_pct=estimate,
                    historical_error_lower_pct=lower,
                    historical_error_upper_pct=upper,
                    risk=risk,
                    risk_unstable=unstable,
                    eligible=True,
                    quality=quality,
                    pre_clip_abstention_pct=pre_clip,
                    model_run_id=model_run_id,
                )
            )
        else:
            exclusion = exclusion_by_code.get(code)
            reasons = list(exclusion.reasons) if exclusion is not None else ["missing_lag"]
            quality = QualityDecision(
                eligible=False,
                reasons=reasons,
                identity_status=getattr(ident, "identity_status", None),
                footprint_status=getattr(ident, "footprint_status", None),
            )
            records.append(
                PredictionRecord(
                    territory_id=territory_id("14", code),
                    municipality_code=code,
                    municipality_name=name,
                    target_year=TARGET_YEAR,
                    estimated_abstention_pct=None,
                    historical_error_lower_pct=None,
                    historical_error_upper_pct=None,
                    risk="insufficient",
                    risk_unstable=False,
                    eligible=False,
                    quality=quality,
                    pre_clip_abstention_pct=None,
                    model_run_id=model_run_id,
                )
            )

    # 6) Artifact payloads.
    model_payload = _model_payload(
        family=family,
        data_hash=data_hash,
        model_run_id=model_run_id,
        fitted=fitted_final,
        candidate_m1=selection.fitted_m1,
        candidate_m1_evaluation={
            "mae_2021": selection.m1.mae,
            "n_2021": selection.m1.n,
            "mae_2024": m1_2024.mae,
            "n_2024": m1_2024.n,
        },
        raw_final=raw_final,
        pred_final=pred_final,
        datasets=datasets,
        explanations=(
            _explanations(fitted_final, datasets[2027])
            if fitted_final is not None
            else _m0_explanations(datasets[2027])
        ),
        candidate_m1_explanations=_explanations(
            selection.fitted_m1, datasets[2027]
        ),
    )
    evaluation_payload = _evaluation_payload(
        family=family,
        selection=selection,
        m0_2024=m0_2024,
        m1_2024=m1_2024,
        amplitude=amplitude,
        datasets=datasets,
        observations=observations,
        data_hash=data_hash,
        errors_2024=errors_2024,
    )
    manifest_payload = _manifest_payload(
        family=family,
        model_run_id=model_run_id,
        data_hash=data_hash,
        identity=model_identity,
    )

    bundle = ModelBundle(
        model_run_id=model_run_id,
        family=family,
        target_year=TARGET_YEAR,
        predictions=tuple(records),
        exclusions=tuple(datasets[2027].exclusions),
        candidate_count=len(datasets[2027].rows),
        total_count=len(records),
        model_payload=model_payload,
        evaluation_payload=evaluation_payload,
        manifest_payload=manifest_payload,
        data_aggregate_sha256=data_hash,
    )

    write_artifacts(bundle, Path(output_dir))
    return bundle


def _model_payload(
    *,
    family: str,
    data_hash: str,
    model_run_id: UUID,
    fitted: FittedRidge | None,
    candidate_m1: FittedRidge | None,
    candidate_m1_evaluation: dict,
    raw_final: np.ndarray,
    pred_final: np.ndarray,
    datasets: dict[int, FeatureDataset],
    explanations: list[dict] | None,
    candidate_m1_explanations: list[dict],
) -> dict:
    payload: dict = {
        "family": family,
        "target_year": TARGET_YEAR,
        "reference_date": "2025-12-15",
        "feature_order": list(FEATURE_ORDER),
        "alpha": ALPHA,
        "data_aggregate_sha256": data_hash,
        "model_run_id": str(model_run_id),
        "pre_clip_outputs_2027": [
            {
                "municipality_code": row.municipality_code,
                "pre_clip": float(raw_final[i]),
                "clipped": float(pred_final[i]),
            }
            for i, row in enumerate(datasets[2027].rows)
        ],
        "clipped_count_2027": int(np.count_nonzero(raw_final != pred_final)),
        "features_2027": [
            {
                "municipality_code": row.municipality_code,
                "municipality_name": row.municipality_name,
                "features": dict(row.features),
                "origins": dict(row.origins),
            }
            for row in datasets[2027].rows
        ],
        "explanations": explanations,
        "candidate_m1_explanations": candidate_m1_explanations,
        "limitations": [
            "Reference cartography 2025-12-15; identity_status=verified_catalogue "
            "is a prerequisite and footprint_status=not_verified (no historical "
            "boundary equality verified).",
            "Association only; coefficients are additive contributions in the "
            "transformed scale and carry no causal interpretation.",
        ],
    }
    if fitted is not None:
        payload["intercept"] = fitted.intercept
        payload["coefficients"] = list(fitted.coefficients)
        payload["scaler"] = {
            "mean": list(fitted.scaler_mean),
            "scale": list(fitted.scaler_scale),
        }
    else:
        payload["description"] = (
            "M0 reference: same-municipality same-type abstention at t-6 (2021)."
        )
    if candidate_m1 is not None:
        payload["candidate_m1"] = {
            "note": (
                "Candidate with sociodemographics (not selected unless the "
                "evaluation selected M1); fitted on 2015/2018 for the 2021 "
                "selection. Contributions are associations, never causes."
            ),
            "intercept": candidate_m1.intercept,
            "coefficients": list(candidate_m1.coefficients),
            "scaler": {
                "mean": list(candidate_m1.scaler_mean),
                "scale": list(candidate_m1.scaler_scale),
            },
            "evaluation": dict(candidate_m1_evaluation),
        }
    return payload


def _evaluation_payload(
    *,
    family: str,
    selection: EvaluationBundle,
    m0_2024: ModelMetrics,
    m1_2024: ModelMetrics,
    amplitude: float | None,
    datasets: dict[int, FeatureDataset],
    observations: list[MunicipalObservation],
    data_hash: str,
    errors_2024: Sequence[float],
) -> dict:
    def metrics(m: ModelMetrics) -> dict:
        return {
            "n": m.n,
            "mae": m.mae,
            "rmse": m.rmse,
            "bias": m.bias,
            "weighted_mae": m.weighted_mae,
            "clipped_count": m.clipped_count,
            "clipped_total": m.clipped_total,
        }

    ln_by_code_year: dict[int, dict[str, int]] = {}
    for obs in observations:
        ln_by_code_year.setdefault(obs.year, {})[obs.key.municipality_code] = obs.ln

    def ln_coverage(target_year: int, eligible_codes: list[str]) -> tuple:
        # 2027 has no observed LN; use the most recent antecedent (2024) as the
        # coverage base and document it.
        base_year = target_year if target_year != 2027 else 2024
        ln_by_code = ln_by_code_year.get(base_year, {})
        total_ln = sum(ln_by_code.values()) if ln_by_code else None
        eligible_ln = (
            sum(ln_by_code[c] for c in eligible_codes if c in ln_by_code)
            if ln_by_code
            else None
        )
        return total_ln, eligible_ln

    cohorts: dict[str, dict] = {}
    exclusions: dict[str, list[dict]] = {}
    for year in (2015, 2018, 2021, 2024, 2027):
        ds = datasets[year]
        eligible_codes = [row.municipality_code for row in ds.rows]
        total_ln, eligible_ln = ln_coverage(year, eligible_codes)
        cohorts[str(year)] = {
            "eligible_count": len(ds.rows),
            "excluded_count": len(ds.exclusions),
            "total_count": len(ln_by_code_year.get(year, {})) if year != 2027 else 125,
            "eligible_ln": eligible_ln,
            "total_ln": total_ln,
        }
        if year == 2027:
            cohorts[str(year)]["ln_coverage_base_year"] = 2024
        exclusions[str(year)] = [
            {"municipality_code": e.municipality_code, "reasons": list(e.reasons)}
            for e in ds.exclusions
        ]

    return {
        "selected_family": selection.selected_family,
        "validation_year": VALIDATION_YEAR,
        "test_year": TEST_YEAR,
        "selection": {
            "m0_mae_2021": selection.m0.mae,
            "m1_mae_2021": selection.m1.mae,
        },
        "metrics": {
            "m0": {"2021": metrics(selection.m0), "2024": metrics(m0_2024)},
            "m1": {"2021": metrics(selection.m1), "2024": metrics(m1_2024)},
        },
        "band": {
            "amplitude_pp": amplitude,
            "n_errors_2021": len(selection.m0_errors),
            "label": "historical error reference (rango de error histórico de referencia)",
            "empirical_coverage_2024": empirical_coverage(errors_2024, amplitude),
            "errors_2021": [
                {
                    "municipality_code": dataset.municipality_code,
                    "error_pp": float(error),
                }
                for dataset, error in zip(
                    datasets[2021].rows,
                    selection.m1_errors if family == "M1" else selection.m0_errors,
                    strict=True,
                )
            ],
            "errors_2024": [
                {
                    "municipality_code": dataset.municipality_code,
                    "error_pp": float(error),
                }
                for dataset, error in zip(
                    datasets[2024].rows, errors_2024, strict=True
                )
            ],
        },
        "cohorts": cohorts,
        "exclusions": exclusions,
        "data_aggregate_sha256": data_hash,
        "note": (
            "2024 is evaluated only after the family is frozen; it never changes "
            "the family, variables, alpha or thresholds."
        ),
    }


def _manifest_payload(
    *,
    family: str,
    model_run_id: UUID,
    data_hash: str,
    identity: dict,
) -> dict:
    import platform

    import numpy as _np
    import pandas as _pd
    import pyarrow as _pa
    import sklearn as _sk

    # The logical hash covers the same canonical identity as ``model_run_id``.
    logical_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return {
        "model_run_id": str(model_run_id),
        "family": family,
        "reference_date": "2025-12-15",
        "data_aggregate_sha256": data_hash,
        "logical_hash": logical_hash,
        "versions": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numpy": _np.__version__,
            "pandas": _pd.__version__,
            "pyarrow": _pa.__version__,
            "scikit_learn": _sk.__version__,
        },
        "limitations": [
            "Historical-error band is the P90 absolute error of the selected "
            "family on 2021; it does not promise 90% future coverage.",
            "Only three elections of each type exist; spatial dependence and "
            "distribution shift limit interpretation.",
            "Catalogue identity (verified_catalogue) does not prove historical "
            "boundary equality (footprint_status=not_verified).",
        ],
    }
