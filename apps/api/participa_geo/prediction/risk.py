"""Analytical risk classification and the historical-error band.

The traffic light is normative (Spec §8): low <40, medium 40-<50, high >=50, and
``insufficient`` when a municipality is not eligible or its estimate is unknown.
The uncertainty band is the P90 of the absolute errors of the selected family on
2021 (the intermediate election), symmetric, clipped to 0-100, and only published
with at least 30 municipalities of eligible error. It is a *historical error
reference*, never a "90% confidence" interval.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np

RiskLevel = Literal["low", "medium", "high", "insufficient"]

#: Label for the band; must never claim a future coverage ("90% confidence").
ERROR_BAND_LABEL = "historical error reference (rango de error histórico de referencia)"

#: Minimum number of eligible errors before a band may be published (Spec §8).
MIN_ERRORS_FOR_BAND = 30

#: Risk thresholds (percentage points, normative).
LOW_THRESHOLD = 40.0
HIGH_THRESHOLD = 50.0


def classify_risk(value: float | None, eligible: bool) -> RiskLevel:
    """Classify an abstention estimate into the analytical traffic light.

    ``None`` or an ineligible municipality is always ``insufficient`` — never a
    numeric zero or a guessed category.
    """
    if not eligible or value is None:
        return "insufficient"
    if value < LOW_THRESHOLD:
        return "low"
    if value < HIGH_THRESHOLD:
        return "medium"
    return "high"


def error_band_amplitude(errors: Sequence[float]) -> float | None:
    """P90 of absolute errors, or ``None`` when fewer than 30 errors exist."""
    absolute = np.abs(np.asarray(errors, dtype=np.float64))
    if absolute.size < MIN_ERRORS_FOR_BAND:
        return None
    return float(np.percentile(absolute, 90.0))


def empirical_coverage(
    errors: Sequence[float],
    amplitude: float | None,
    *,
    minimum: int = MIN_ERRORS_FOR_BAND,
) -> dict[str, float | int] | None:
    """Empirical coverage of a band against out-of-time errors.

    The amplitude is *never* adjusted with these errors (Spec §8): this is a
    descriptive check of how many 2024 absolute errors fall inside the 2021 P90
    band. It is not published when fewer than ``minimum`` usable errors exist.
    """
    if amplitude is None:
        return None
    absolute = np.abs(np.asarray(errors, dtype=np.float64))
    n = int(absolute.size)
    if n < minimum:
        return None
    within = int(np.count_nonzero(absolute <= amplitude))
    return {
        "n": n,
        "within": within,
        "share": within / n,
        "amplitude_pp": float(amplitude),
        "minimum_n": minimum,
    }


def risk_band(
    estimate: float | None, amplitude: float | None
) -> tuple[float | None, float | None]:
    """Symmetric band ``estimate ± amplitude``, clipped to 0-100."""
    if estimate is None or amplitude is None:
        return (None, None)
    lower = min(100.0, max(0.0, estimate - amplitude))
    upper = min(100.0, max(0.0, estimate + amplitude))
    return (lower, upper)


def is_risk_unstable(lower: float | None, upper: float | None) -> bool:
    """True when the band straddles a risk threshold (category is not settled)."""
    if lower is None or upper is None:
        return False
    return (lower < LOW_THRESHOLD <= upper) or (lower < HIGH_THRESHOLD <= upper)


__all__ = [
    "ERROR_BAND_LABEL",
    "HIGH_THRESHOLD",
    "LOW_THRESHOLD",
    "MIN_ERRORS_FOR_BAND",
    "RiskLevel",
    "classify_risk",
    "empirical_coverage",
    "error_band_amplitude",
    "is_risk_unstable",
    "risk_band",
]
