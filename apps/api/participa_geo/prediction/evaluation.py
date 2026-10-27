"""Evaluation metrics for the abstention model.

MAE and RMSE are in percentage points; bias is ``mean(prediction - target)``.
Weighted MAE weights each municipality by the target year's known denominator
(``SV + NV``) as a secondary indicator. All computations are float64 and
deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ModelMetrics:
    """Metrics for one model on one evaluation cut."""

    n: int
    mae: float
    rmse: float
    bias: float
    weighted_mae: float | None
    clipped_count: int = 0
    clipped_total: int = 0


def compute_metrics(
    y_true: Sequence[float],
    y_pred: Sequence[float],
    weights: Sequence[float] | None = None,
    *,
    clipped_count: int = 0,
) -> ModelMetrics:
    """Compute MAE/RMSE/bias and (optionally) weighted MAE.

    ``weights`` is the target known denominator per municipality; when all
    weights are zero (no target) the weighted MAE is ``None``.
    """
    true = np.asarray(y_true, dtype=np.float64)
    pred = np.asarray(y_pred, dtype=np.float64)
    errors = pred - true
    absolute = np.abs(errors)

    n = int(true.size)
    mae = float(np.mean(absolute))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    bias = float(np.mean(errors))

    weighted_mae: float | None = None
    if weights is not None and n > 0:
        w = np.asarray(weights, dtype=np.float64)
        if w.sum() > 0:
            weighted_mae = float(np.sum(w * absolute) / np.sum(w))

    return ModelMetrics(
        n=n,
        mae=mae,
        rmse=rmse,
        bias=bias,
        weighted_mae=weighted_mae,
        clipped_count=clipped_count,
        clipped_total=n,
    )


__all__ = ["ModelMetrics", "compute_metrics"]
