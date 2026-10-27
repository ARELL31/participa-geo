"""Unit tests for neutral, versioned preventive recommendations (T6)."""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from participa_geo.db.models import PredictionRecord
from participa_geo.prediction.risk import classify_risk, is_risk_unstable
from participa_geo.recommendations.rules import RECOMMENDATION_RULES_VERSION, recommend

MODEL_RUN_ID = UUID("00000000-0000-0000-0000-0000000000aa")


def make_prediction(
    code: str,
    abstention: float | None,
    *,
    eligible: bool = True,
    band: tuple[float, float] | None = None,
    reasons: list[str] | None = None,
    unstable: bool | None = None,
) -> PredictionRecord:
    territory_id = uuid5(NAMESPACE_URL, f"participa-geo:test-recommendation:{code}")
    if eligible and abstention is not None:
        lower, upper = band if band is not None else (
            max(0.0, abstention - 2.0),
            min(100.0, abstention + 2.0),
        )
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
        target_year=2027,
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


def test_high_unknown_share_is_a_data_quality_action_not_political_optimisation():
    prediction = make_prediction(
        "001", 55.0, reasons=["high_unknown_share"], unstable=True
    )

    rules = recommend(prediction)

    codes = {rule.code for rule in rules}
    assert "improve_data_quality" in codes
    data_rule = next(rule for rule in rules if rule.code == "improve_data_quality")
    assert "high_unknown_share" in data_rule.reasons
    assert "datos" in data_rule.action.lower() or "calidad" in data_rule.action.lower()
    assert all(rule.version == RECOMMENDATION_RULES_VERSION for rule in rules)

    text = " ".join(
        f"{rule.title} {rule.action} {' '.join(rule.reasons)}" for rule in rules
    ).lower()
    for forbidden in ("presupuesto", "partido", "movilizar", "segmentar", "campaña"):
        assert forbidden not in text


def test_insufficient_prediction_points_to_data_improvement():
    prediction = make_prediction("002", None, eligible=False, reasons=["missing_lag"])

    rules = recommend(prediction)

    assert [rule.code for rule in rules] == ["improve_data_quality"]
    assert "missing_lag" in rules[0].reasons
    assert rules[0].priority == "data"


def test_high_risk_recommends_institutional_review_without_budget_optimisation():
    prediction = make_prediction("003", 55.0, unstable=False)

    rules = recommend(prediction)
    codes = {rule.code for rule in rules}

    assert "institutional_review" in codes
    review = next(rule for rule in rules if rule.code == "institutional_review")
    assert "institucional" in review.action.lower()
    assert "presupuesto" not in review.action.lower()
    assert (
        "no constituye" in review.action.lower()
        or "no es una obligación" in review.action.lower()
    )


def test_unstable_category_is_monitored():
    prediction = make_prediction("004", 49.0, band=(47.0, 51.0), unstable=True)

    rules = recommend(prediction)

    assert "monitor_unstable_category" in {rule.code for rule in rules}


def test_medium_and_low_risk_have_versioned_monitoring_rules():
    medium = recommend(make_prediction("005", 45.0))
    low = recommend(make_prediction("006", 30.0))

    assert "preventive_monitoring" in {rule.code for rule in medium}
    assert "maintain_monitoring" in {rule.code for rule in low}
    assert all(rule.version for rule in medium + low)
