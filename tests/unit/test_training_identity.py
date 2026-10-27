"""Regression tests for the canonical ``model_run_id`` identity (review item 2).

The identifier must change when any published evidence changes: identity
statuses, cohort membership/exclusions, candidate M1 parameters, or either
evaluation. It is a hash over canonical content, never a reusable timestamp.
"""

from __future__ import annotations

import copy

from participa_geo.ingestion.schema import FootprintStatus, IdentityStatus
from participa_geo.prediction.artifacts import compute_model_run_id
from participa_geo.prediction.cohorts import Exclusion, TerritoryIdentity
from participa_geo.prediction.evaluation import ModelMetrics
from participa_geo.prediction.features import FeatureDataset
from participa_geo.prediction.training import (
    EvaluationBundle,
    FittedRidge,
    build_model_identity,
)

METRICS = ModelMetrics(
    n=91, mae=4.93, rmse=5.65, bias=-4.72, weighted_mae=3.80
)


def _fitted(intercept: float) -> FittedRidge:
    return FittedRidge(
        intercept=intercept,
        coefficients=(0.1,) * 6,
        scaler_mean=(0.0,) * 6,
        scaler_scale=(1.0,) * 6,
    )


def _selection(intercept: float = 36.33) -> EvaluationBundle:
    return EvaluationBundle(
        validation_year=2021,
        m0=METRICS,
        m1=METRICS,
        selected_family="M0",
        m0_errors=(0.0,) * 91,
        m1_errors=(1.0,) * 91,
        fitted_m1=_fitted(intercept),
    )


def _identity(
    *,
    statuses: dict[str, TerritoryIdentity] | None = None,
    datasets: dict[int, FeatureDataset] | None = None,
    selection: EvaluationBundle | None = None,
):
    return build_model_identity(
        family="M0",
        data_hash="a" * 64,
        identity_statuses=statuses or {},
        datasets=datasets or {},
        selection=selection or _selection(),
        m0_2024=METRICS,
        m1_2024=METRICS,
        amplitude=8.56,
        fitted_final=None,
    )


def test_identity_status_changes_model_run_id():
    verified = {
        "001": TerritoryIdentity(
            IdentityStatus.verified_catalogue, FootprintStatus.not_verified
        )
    }
    changed = {
        "001": TerritoryIdentity(
            IdentityStatus.known_changed, FootprintStatus.not_verified
        )
    }
    assert compute_model_run_id(_identity(statuses=verified)) != compute_model_run_id(
        _identity(statuses=changed)
    )


def test_candidate_m1_parameters_and_evaluation_change_model_run_id():
    base = _identity()
    changed_parameters = copy.deepcopy(base)
    changed_parameters["candidate_m1"]["intercept"] += 1.0
    assert compute_model_run_id(base) != compute_model_run_id(changed_parameters)

    changed_evaluation = copy.deepcopy(base)
    changed_evaluation["metrics"]["m1"]["2021"]["mae"] += 1.0
    assert compute_model_run_id(base) != compute_model_run_id(changed_evaluation)


def test_cohort_and_exclusion_change_model_run_id():
    eligible = FeatureDataset(2027, (), ())
    excluded = FeatureDataset(
        2027,
        (),
        (
            Exclusion(
                municipality_code="001",
                municipality_name="ACATIC",
                reasons=("high_unknown_share",),
                identity_status=IdentityStatus.verified_catalogue,
                footprint_status=FootprintStatus.not_verified,
            ),
        ),
    )
    assert compute_model_run_id(
        _identity(datasets={2027: eligible})
    ) != compute_model_run_id(_identity(datasets={2027: excluded}))
