"""Pure scenario arithmetic and closed assumption catalogue (T6).

No database, model training or causal estimation lives here. ``B`` is only
``max(0, A - reduction_pp)`` for the selected eligible municipalities; all other
municipalities keep ``A`` and insufficient predictions stay ``null``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from participa_geo.api.schemas.scenarios import (
    TRANSLATED_BAND_LABEL,
    ScenarioComparison,
    ScenarioRequest,
    ScenarioResultDTO,
)
from participa_geo.db.models import PredictionRecord
from participa_geo.prediction.risk import classify_risk, is_risk_unstable

SCENARIO_RULES_VERSION = "scenario-rules-1.0.0"


@dataclass(frozen=True)
class AssumptionTemplate:
    """A reviewed assumption code with its fixed explanatory text."""

    code: str
    version: str
    text: str


ASSUMPTION_CATALOG: dict[str, AssumptionTemplate] = {
    "preventive_exploration": AssumptionTemplate(
        code="preventive_exploration",
        version="1.0",
        text=(
            "Supuesto de exploración preventiva: la reducción solicitada es un "
            "ejercicio aritmético de sensibilidad sobre municipios seleccionados; "
            "no representa una eficacia causal demostrada ni una proyección de "
            "personas movilizadas."
        ),
    ),
    "model_sensitivity": AssumptionTemplate(
        code="model_sensitivity",
        version="1.0",
        text=(
            "Supuesto de sensibilidad del modelo: se compara un cambio hipotético "
            "acotado para observar si la clasificación de riesgo cambia; no agrega "
            "evidencia causal ni cuantifica la incertidumbre del efecto."
        ),
    ),
}


class ScenarioInputError(ValueError):
    """A closed-input validation failure with per-identifier reasons."""

    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__("La solicitud de escenario no supera la validación.")
        self.errors = errors


class ScenarioConflictError(RuntimeError):
    """The database state cannot serve a scenario (e.g. no published model)."""


def _input_error(
    *,
    reason: str,
    message: str,
    territory_id: object | None = None,
    model_run_id: object | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "loc": ["body", "territory_ids"] if territory_id is not None else ["body"],
        "msg": message,
        "type": "value_error",
        "reason": reason,
    }
    if territory_id is not None:
        error["territory_id"] = str(territory_id)
    if model_run_id is not None:
        error["model_run_id"] = str(model_run_id)
    return error


def _clip(value: float) -> float:
    return min(100.0, max(0.0, value))


def _translated_band(
    lower: float | None,
    upper: float | None,
    effective_reduction_pp: float,
) -> tuple[float | None, float | None]:
    if lower is None or upper is None:
        return (None, None)
    return (
        _clip(lower - effective_reduction_pp),
        _clip(upper - effective_reduction_pp),
    )


def _validate_request(request: ScenarioRequest) -> None:
    errors: list[dict[str, Any]] = []
    reduction = request.reduction_pp
    if not math.isfinite(reduction) or reduction < 0.0 or reduction > 10.0:
        errors.append(
            _input_error(
                reason="reduction_out_of_range",
                message="reduction_pp debe ser finita y estar entre 0 y 10.",
            )
        )
    if request.target_year != 2027:
        errors.append(
            _input_error(
                reason="target_year_not_supported",
                message="target_year debe ser 2027.",
            )
        )
    if not request.territory_ids or len(request.territory_ids) > 125:
        errors.append(
            _input_error(
                reason="territory_selection_size",
                message="territory_ids debe contener entre 1 y 125 identificadores.",
            )
        )
    if len(set(request.territory_ids)) != len(request.territory_ids):
        errors.append(
            _input_error(
                reason="duplicate_territory",
                message="territory_ids debe contener identificadores únicos.",
            )
        )
    if errors:
        raise ScenarioInputError(errors)


def _input_sha256(
    predictions: Sequence[PredictionRecord], request: ScenarioRequest
) -> str:
    payload = {
        "model_run_id": str(request.model_run_id),
        "target_year": request.target_year,
        "territory_ids": sorted(str(t) for t in request.territory_ids),
        "reduction_pp": request.reduction_pp,
        "assumption_code": request.assumption_code,
        "predictions": [
            {
                "territory_id": str(prediction.territory_id),
                "estimated_abstention_pct": prediction.estimated_abstention_pct,
                "historical_error_lower_pct": prediction.historical_error_lower_pct,
                "historical_error_upper_pct": prediction.historical_error_upper_pct,
                "risk": prediction.risk,
                "risk_unstable": prediction.risk_unstable,
                "eligible": prediction.eligible,
            }
            for prediction in sorted(
                predictions, key=lambda item: str(item.territory_id)
            )
        ],
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def simulate_scenario(
    predictions: Sequence[PredictionRecord], request: ScenarioRequest
) -> ScenarioComparison:
    """Compute the persisted A/B comparison without training or estimating effects."""
    _validate_request(request)
    if request.assumption_code not in ASSUMPTION_CATALOG:
        raise ScenarioInputError(
            [
                _input_error(
                    reason="assumption_not_in_catalogue",
                    message="assumption_code no está en el catálogo controlado.",
                )
            ]
        )

    by_id = {prediction.territory_id: prediction for prediction in predictions}
    selected_ids = set(request.territory_ids)
    errors: list[dict[str, Any]] = []

    for territory_id in request.territory_ids:
        prediction = by_id.get(territory_id)
        if prediction is None:
            errors.append(
                _input_error(
                    reason="unknown_territory",
                    message="El territorio no pertenece al universo de predicciones.",
                    territory_id=territory_id,
                )
            )
            continue
        if prediction.model_run_id != request.model_run_id:
            errors.append(
                _input_error(
                    reason="model_run_mismatch",
                    message="La predicción no pertenece a la ejecución de modelo solicitada.",
                    territory_id=territory_id,
                )
            )
            continue
        if prediction.target_year != request.target_year:
            errors.append(
                _input_error(
                    reason="target_year_mismatch",
                    message="La predicción no corresponde al año objetivo solicitado.",
                    territory_id=territory_id,
                )
            )
            continue
        if not prediction.eligible or prediction.estimated_abstention_pct is None:
            errors.append(
                _input_error(
                    reason="ineligible_territory",
                    message=(
                        "El territorio tiene información insuficiente y no puede "
                        "seleccionarse en un escenario."
                    ),
                    territory_id=territory_id,
                )
            )
    if errors:
        raise ScenarioInputError(errors)

    assumption = ASSUMPTION_CATALOG[request.assumption_code]
    reduction = request.reduction_pp
    results: list[ScenarioResultDTO] = []

    for prediction in sorted(
        predictions,
        key=lambda item: (
            item.state_code,
            item.territory_code or item.municipality_code or "",
        ),
    ):
        baseline = prediction.estimated_abstention_pct
        eligible = prediction.eligible and baseline is not None
        selected = prediction.territory_id in selected_ids

        if selected:
            assert baseline is not None  # validated above
            hypothetical = max(0.0, baseline - reduction)
        else:
            hypothetical = baseline

        if baseline is None or hypothetical is None:
            effective = 0.0
        else:
            effective = baseline - hypothetical

        baseline_lower = prediction.historical_error_lower_pct
        baseline_upper = prediction.historical_error_upper_pct
        hypothetical_lower, hypothetical_upper = _translated_band(
            baseline_lower, baseline_upper, effective
        )

        risk_a = prediction.risk or classify_risk(baseline, eligible)
        if selected:
            risk_b = classify_risk(hypothetical, eligible)
            risk_b_unstable = is_risk_unstable(hypothetical_lower, hypothetical_upper)
        else:
            # Unselected territories are exactly unchanged, including metadata.
            risk_b = risk_a
            risk_b_unstable = prediction.risk_unstable

        results.append(
            ScenarioResultDTO(
                territory_id=prediction.territory_id,
                municipality_code=prediction.municipality_code,
                municipality_name=prediction.municipality_name,
                state_code=prediction.state_code,
                level=prediction.level,
                territory_code=prediction.territory_code or prediction.municipality_code,
                district_plan=prediction.district_plan,
                baseline_abstention_pct=baseline,
                hypothetical_abstention_pct=hypothetical,
                baseline_error_lower_pct=baseline_lower,
                baseline_error_upper_pct=baseline_upper,
                hypothetical_error_lower_pct=hypothetical_lower,
                hypothetical_error_upper_pct=hypothetical_upper,
                requested_reduction_pp=reduction,
                effective_reduction_pp=effective,
                risk_a=risk_a,
                risk_b=risk_b,
                risk_a_unstable=prediction.risk_unstable,
                risk_b_unstable=risk_b_unstable,
                selected=selected,
            )
        )

    return ScenarioComparison(
        model_run_id=request.model_run_id,
        target_year=request.target_year,
        requested_reduction_pp=reduction,
        assumption_code=request.assumption_code,
        level=request.level or (predictions[0].level if predictions else "municipality"),
        district_plan=predictions[0].district_plan if predictions else None,
        assumption_version=assumption.version,
        rationale_text=assumption.text,
        rules_version=SCENARIO_RULES_VERSION,
        input_sha256=_input_sha256(predictions, request),
        error_band_label=TRANSLATED_BAND_LABEL,
        selected_territory_ids=sorted(request.territory_ids, key=str),
        results=results,
    )


__all__ = [
    "ASSUMPTION_CATALOG",
    "SCENARIO_RULES_VERSION",
    "TRANSLATED_BAND_LABEL",
    "AssumptionTemplate",
    "ScenarioConflictError",
    "ScenarioInputError",
    "simulate_scenario",
]
