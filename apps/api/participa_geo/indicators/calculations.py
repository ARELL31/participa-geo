"""Participation indicators and quality decisions.

``unknown_share`` is a fraction 0-1; the other indicators are percentage points
0-100. ``NS`` is never reclassified as abstention: participation/abstention use
``SV + NV`` as denominator, while the ``NS`` sensitivity bounds use ``LN``.
"""

from __future__ import annotations

from dataclasses import dataclass

from participa_geo.ingestion.schema import (
    FootprintStatus,
    IdentityStatus,
    MunicipalObservation,
)

#: Quality rule (Spec §6): a municipality/year is eligible when ``SV + NV >= 1000``
#: and ``NS / LN <= 0.10`` with valid counts.
MIN_KNOWN_COUNT = 1000
MAX_UNKNOWN_SHARE = 0.10


@dataclass(frozen=True)
class IndicatorValues:
    participation_pct: float | None
    abstention_pct: float | None
    unknown_share: float | None
    ns_lower_pct: float | None
    ns_upper_pct: float | None


@dataclass(frozen=True)
class QualityDecision:
    eligible: bool
    reasons: list[str]
    identity_status: IdentityStatus | None = None
    footprint_status: FootprintStatus | None = None


def calculate_indicators(ln: int, sv: int, nv: int, ns: int) -> IndicatorValues:
    """Compute participation, abstention and ``NS`` sensitivity from summed counts.

    Zero denominators return ``None`` (never a default zero).
    """
    known = sv + nv
    participation_pct = (100.0 * sv / known) if known > 0 else None
    abstention_pct = (100.0 * nv / known) if known > 0 else None

    if ln > 0:
        unknown_share = ns / ln
        ns_lower_pct = 100.0 * nv / ln
        ns_upper_pct = 100.0 * (nv + ns) / ln
    else:
        unknown_share = ns_lower_pct = ns_upper_pct = None

    return IndicatorValues(
        participation_pct=participation_pct,
        abstention_pct=abstention_pct,
        unknown_share=unknown_share,
        ns_lower_pct=ns_lower_pct,
        ns_upper_pct=ns_upper_pct,
    )


def assess_quality(observation: MunicipalObservation) -> QualityDecision:
    """Apply the count-based quality rule (geographic statuses stay ``None`` in T2).

    Stable reasons: ``invalid_counts``, ``zero_denominator``, ``small_known_count``,
    ``high_unknown_share``. The geographic identity/footprint states are completed
    by T3 and are deliberately ``None`` here (``None`` never means verified).
    """
    ln, sv, nv, ns = observation.ln, observation.sv, observation.nv, observation.ns
    if ln < 0 or sv < 0 or nv < 0 or ns < 0 or ln != sv + nv + ns:
        return QualityDecision(eligible=False, reasons=["invalid_counts"])

    known = sv + nv
    if known == 0:
        return QualityDecision(eligible=False, reasons=["zero_denominator"])

    reasons: list[str] = []
    if known < MIN_KNOWN_COUNT:
        reasons.append("small_known_count")
    if ln > 0 and ns / ln > MAX_UNKNOWN_SHARE:
        reasons.append("high_unknown_share")

    return QualityDecision(eligible=not reasons, reasons=reasons)


__all__ = [
    "IndicatorValues",
    "QualityDecision",
    "calculate_indicators",
    "assess_quality",
]
