"""Fixed, versioned preventive recommendation rules (T6).

The rules are readable and neutral: improve data quality where the unknown share
is high, consider civic information/institutional review at high risk, monitor
unstable categories, and keep the equity caveat visible. There is deliberately
no budget optimisation, persuasive segmentation or individual-level inference.
"""

from __future__ import annotations

from participa_geo.api.schemas.scenarios import Recommendation
from participa_geo.db.models import PredictionRecord
from participa_geo.prediction.risk import classify_risk

RECOMMENDATION_RULES_VERSION = "recommendation-rules-1.0.0"

_DATA_REASONS = frozenset(
    {
        "high_unknown_share",
        "zero_denominator",
        "small_known_count",
        "invalid_counts",
        "missing_lag",
        "insufficient_error_history",
        "ambiguous_identity",
        "known_administrative_change",
    }
)


def _quality_reasons(prediction: PredictionRecord) -> list[str]:
    quality = prediction.quality or {}
    return [str(reason) for reason in quality.get("reasons", [])]


def _rule(
    code: str,
    priority: str,
    title: str,
    action: str,
    reasons: list[str],
) -> Recommendation:
    return Recommendation(
        code=code,
        version=RECOMMENDATION_RULES_VERSION,
        priority=priority,  # type: ignore[arg-type]
        title=title,
        action=action,
        reasons=reasons,
    )


def recommend(prediction: PredictionRecord) -> list[Recommendation]:
    """Return the fixed rule outputs for one persisted prediction."""
    reasons = _quality_reasons(prediction)
    risk = prediction.risk or classify_risk(
        prediction.estimated_abstention_pct, prediction.eligible
    )
    eligible = (
        prediction.eligible and prediction.estimated_abstention_pct is not None
    )

    if not eligible or risk == "insufficient":
        return [
            _rule(
                "improve_data_quality",
                "data",
                "Mejorar datos antes de priorizar",
                (
                    "Revisar la calidad y completar la información del territorio "
                    "antes de usarlo para priorización; no imputar un valor numérico "
                    "ni presentar la ausencia como abstención cero."
                ),
                reasons or ["insufficient_information"],
            )
        ]

    recommendations: list[Recommendation] = []

    data_reasons = [reason for reason in reasons if reason in _DATA_REASONS]
    if data_reasons:
        recommendations.append(
            _rule(
                "improve_data_quality",
                "data",
                "Revisar calidad de datos",
                (
                    "Revisar la calidad de los datos del territorio, en particular "
                    "la proporción de no especificados y la cobertura de antecedentes, "
                    "antes de interpretar el resultado como prioridad."
                ),
                data_reasons,
            )
        )

    if risk == "high":
        recommendations.append(
            _rule(
                "institutional_review",
                "high",
                "Considerar revisión institucional",
                (
                    "Considerar información cívica y revisión institucional; no "
                    "constituye una obligación ni una asignación de recursos."
                ),
                ["risk_high"],
            )
        )
    elif risk == "medium":
        recommendations.append(
            _rule(
                "preventive_monitoring",
                "medium",
                "Mantener seguimiento preventivo",
                (
                    "Mantener seguimiento preventivo de la categoría de riesgo y "
                    "revisar la banda de error histórica antes de priorizar."
                ),
                ["risk_medium"],
            )
        )
    else:
        recommendations.append(
            _rule(
                "maintain_monitoring",
                "low",
                "Mantener monitoreo periódico",
                (
                    "Mantener el monitoreo periódico; las reglas actuales no "
                    "identifican una prioridad preventiva adicional."
                ),
                ["risk_low"],
            )
        )

    if prediction.risk_unstable:
        recommendations.append(
            _rule(
                "monitor_unstable_category",
                "context",
                "Monitorear categoría inestable",
                (
                    "Monitorear la categoría inestable: la banda de error histórica "
                    "cruza un umbral y la clasificación no debe presentarse como certeza."
                ),
                ["threshold_crossed_by_historical_band"],
            )
        )

    recommendations.append(
        _rule(
            "coverage_equity_review",
            "context",
            "Evaluar equidad y cobertura",
            (
                "Evaluar la equidad considerando la cobertura territorial y el tamaño "
                "de la lista nominal observada; no inferir conducta individual."
            ),
            ["partial_territorial_coverage"],
        )
    )
    return recommendations


__all__ = ["RECOMMENDATION_RULES_VERSION", "recommend"]
