"""Unit tests for the pure scenario arithmetic (T6).

The fixtures here are synthetic and isolated from the demo database: the first
municipality has 47% abstention, is eligible and is selected in
``request_3_pp``. Nothing in this module writes to PostGIS.
"""

from __future__ import annotations

import math
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from participa_geo.api.schemas.scenarios import ScenarioRequest
from participa_geo.db.models import PredictionRecord
from participa_geo.prediction.risk import classify_risk, is_risk_unstable
from participa_geo.scenarios.rules import (
    TRANSLATED_BAND_LABEL,
    ScenarioInputError,
    simulate_scenario,
)
from participa_geo.scenarios.service import ScenarioRateLimiter, ScenarioRateLimitError

MODEL_RUN_ID = UUID("00000000-0000-0000-0000-0000000000aa")


def _territory(code: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"participa-geo:test-scenario:{code}")


def make_prediction(
    code: str,
    abstention: float | None,
    *,
    eligible: bool = True,
    band: tuple[float, float] | None = None,
    risk: str | None = None,
    unstable: bool | None = None,
    reasons: list[str] | None = None,
    target_year: int = 2027,
) -> PredictionRecord:
    """Build one synthetic prediction row (never persisted)."""
    territory_id = _territory(code)
    if eligible and abstention is not None:
        lower, upper = band if band is not None else (
            max(0.0, abstention - 2.0),
            min(100.0, abstention + 2.0),
        )
        if risk is None:
            risk = classify_risk(abstention, True)
        if unstable is None:
            unstable = is_risk_unstable(lower, upper)
    else:
        eligible = False
        abstention = None
        lower = upper = None
        risk = "insufficient"
        unstable = False
    return PredictionRecord(
        territory_id=territory_id,
        municipality_code=code,
        municipality_name=f"MUNICIPIO {code}",
        target_year=target_year,
        estimated_abstention_pct=abstention,
        historical_error_lower_pct=lower,
        historical_error_upper_pct=upper,
        risk=risk,
        risk_unstable=bool(unstable),
        eligible=eligible,
        quality={
            "eligible": eligible,
            "reasons": list(reasons or []),
            "identity_status": "verified_catalogue",
            "footprint_status": "not_verified",
        },
        model_run_id=MODEL_RUN_ID,
    )


def make_request(
    territory_ids: list[UUID],
    *,
    reduction: float = 3.0,
    assumption_code: str = "preventive_exploration",
    target_year: int = 2027,
    model_run_id: UUID = MODEL_RUN_ID,
) -> ScenarioRequest:
    return ScenarioRequest(
        model_run_id=model_run_id,
        target_year=target_year,
        territory_ids=territory_ids,
        reduction_pp=reduction,
        assumption_code=assumption_code,
    )


@pytest.fixture
def predictions_47_pct() -> list[PredictionRecord]:
    return [make_prediction("001", 47.0)]


@pytest.fixture
def request_3_pp(predictions_47_pct: list[PredictionRecord]) -> ScenarioRequest:
    return make_request([predictions_47_pct[0].territory_id])


def test_reduction_is_percentage_points(predictions_47_pct, request_3_pp):
    result = simulate_scenario(predictions_47_pct, request_3_pp).results[0]
    assert result.baseline_abstention_pct == 47.0
    assert result.hypothetical_abstention_pct == 44.0
    assert result.effective_reduction_pp == 3.0
    assert result.requested_reduction_pp == 3.0
    assert result.selected is True


def test_reduction_clips_at_zero():
    prediction = make_prediction("002", 2.0, band=(0.0, 4.0))
    request = make_request([prediction.territory_id], reduction=3.0)

    result = simulate_scenario([prediction], request).results[0]

    assert result.baseline_abstention_pct == 2.0
    assert result.hypothetical_abstention_pct == 0.0
    assert result.effective_reduction_pp == 2.0
    # The historical reference band is translated by the *effective* shift and
    # clipped, never allowed to become negative.
    assert result.hypothetical_error_lower_pct == 0.0
    assert result.hypothetical_error_upper_pct == 2.0


def test_unselected_territories_unchanged():
    selected = make_prediction("003", 47.0)
    untouched = make_prediction("004", 30.0, band=(28.0, 32.0), unstable=False)
    request = make_request([selected.territory_id], reduction=4.0)

    results = simulate_scenario([selected, untouched], request).results
    by_code = {r.municipality_code: r for r in results}

    assert by_code["003"].selected is True
    assert by_code["003"].hypothetical_abstention_pct == 43.0

    unchanged = by_code["004"]
    assert unchanged.selected is False
    assert unchanged.baseline_abstention_pct == 30.0
    assert unchanged.hypothetical_abstention_pct == 30.0
    assert unchanged.effective_reduction_pp == 0.0
    assert unchanged.baseline_error_lower_pct == 28.0
    assert unchanged.baseline_error_upper_pct == 32.0
    assert unchanged.hypothetical_error_lower_pct == 28.0
    assert unchanged.hypothetical_error_upper_pct == 32.0
    assert unchanged.risk_a == unchanged.risk_b
    assert unchanged.risk_b_unstable == unchanged.risk_a_unstable


def test_insufficient_selected_rejected():
    insufficient = make_prediction("005", None, eligible=False, reasons=["high_unknown_share"])
    request = make_request([insufficient.territory_id])

    with pytest.raises(ScenarioInputError) as excinfo:
        simulate_scenario([insufficient], request)

    errors = excinfo.value.errors
    assert errors, "the rejection must name the offending identifier and cause"
    assert str(insufficient.territory_id) in {str(e.get("territory_id")) for e in errors}
    assert any(e.get("reason") for e in errors)


def test_unselected_insufficient_stays_null():
    eligible = make_prediction("006", 47.0)
    insufficient = make_prediction("007", None, eligible=False)
    request = make_request([eligible.territory_id])

    results = simulate_scenario([eligible, insufficient], request).results
    null_row = next(r for r in results if r.municipality_code == "007")

    assert null_row.selected is False
    assert null_row.baseline_abstention_pct is None
    assert null_row.hypothetical_abstention_pct is None
    assert null_row.effective_reduction_pp == 0.0
    assert null_row.risk_a == "insufficient"
    assert null_row.risk_b == "insufficient"
    assert null_row.hypothetical_error_lower_pct is None
    assert null_row.hypothetical_error_upper_pct is None


def test_band_is_labelled_as_translated_historical_reference():
    prediction = make_prediction("008", 47.0, band=(45.0, 49.0), unstable=False)
    request = make_request([prediction.territory_id], reduction=3.0)

    comparison = simulate_scenario([prediction], request)
    result = comparison.results[0]

    assert result.baseline_error_lower_pct == 45.0
    assert result.baseline_error_upper_pct == 49.0
    assert result.hypothetical_error_lower_pct == 42.0
    assert result.hypothetical_error_upper_pct == 46.0
    assert comparison.error_band_label == TRANSLATED_BAND_LABEL
    assert "histórico" in comparison.error_band_label.lower()
    assert "causal" in comparison.error_band_label.lower()


def test_risk_thresholds_are_identical_for_a_and_b():
    # A=51 high; with 3 pp the hypothetical falls below 50 -> medium. The B band
    # crosses the 50 threshold, so it is flagged unstable without degrading A.
    prediction = make_prediction("009", 51.0, band=(49.0, 53.0), unstable=True)
    request = make_request([prediction.territory_id], reduction=3.0)

    result = simulate_scenario([prediction], request).results[0]

    assert result.risk_a == "high"
    assert result.risk_b == "medium"
    assert result.risk_a_unstable is True
    assert result.risk_b_unstable is True


def test_non_finite_reduction_is_rejected_before_arithmetic():
    prediction = make_prediction("010", 47.0)
    request = make_request([prediction.territory_id], reduction=3.0)
    object.__setattr__(request, "reduction_pp", math.nan)

    with pytest.raises(ScenarioInputError):
        simulate_scenario([prediction], request)


def test_rate_limiter_rejects_eleventh_creation_and_concurrent_request():
    limiter = ScenarioRateLimiter(limit=2, window_seconds=60.0)

    with limiter.acquire("client-a"):
        pass
    with limiter.acquire("client-a"):
        pass
    with pytest.raises(ScenarioRateLimitError):
        with limiter.acquire("client-a"):
            pass

    # A different client has its own budget.
    with limiter.acquire("client-b"):
        pass

    # Only one active request per client.
    with limiter.acquire("client-c"):
        with pytest.raises(ScenarioRateLimitError):
            with limiter.acquire("client-c"):
                pass
