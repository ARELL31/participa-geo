"""Prediction domain: interpretable model, temporal validation and artifacts."""

from participa_geo.prediction.artifacts import ModelBundle, PredictionRecord
from participa_geo.prediction.cohorts import (
    TARGET_YEAR,
    Exclusion,
    IncompleteIdentityError,
    TerritoryIdentity,
    build_cohort,
    read_identity_statuses,
    required_quality_years,
)
from participa_geo.prediction.evaluation import ModelMetrics, compute_metrics
from participa_geo.prediction.features import (
    FEATURE_ORDER,
    ExampleRow,
    FeatureDataset,
    build_examples,
    is_midterm_election,
)
from participa_geo.prediction.risk import (
    RiskLevel,
    classify_risk,
    error_band_amplitude,
    is_risk_unstable,
    risk_band,
)
from participa_geo.prediction.training import (
    ALPHA,
    EvaluationBundle,
    FittedRidge,
    evaluate_models,
    fit_ridge,
    predict_m0,
    predict_ridge,
    select_family,
    train_release,
)

__all__ = [
    "ALPHA",
    "EvaluationBundle",
    "ExampleRow",
    "Exclusion",
    "FEATURE_ORDER",
    "FeatureDataset",
    "FittedRidge",
    "IncompleteIdentityError",
    "ModelBundle",
    "ModelMetrics",
    "PredictionRecord",
    "RiskLevel",
    "TARGET_YEAR",
    "TerritoryIdentity",
    "build_cohort",
    "build_examples",
    "classify_risk",
    "compute_metrics",
    "error_band_amplitude",
    "evaluate_models",
    "fit_ridge",
    "is_midterm_election",
    "is_risk_unstable",
    "predict_m0",
    "predict_ridge",
    "read_identity_statuses",
    "required_quality_years",
    "risk_band",
    "select_family",
    "train_release",
]
