"""Unit tests for the historical-error band and clipping bookkeeping.

The band amplitude is the P90 of the absolute errors of the selected family on
2021 (the intermediate election), and is only published with at least 30
municipalities of eligible error. It is labelled a *historical error reference*,
never a "90% confidence" interval.
"""

from __future__ import annotations

import numpy as np
import pytest

from participa_geo.prediction import risk as risk_mod
from participa_geo.prediction.features import FEATURE_ORDER, ExampleRow, FeatureDataset
from participa_geo.prediction.risk import (
    error_band_amplitude,
    is_risk_unstable,
    risk_band,
)
from participa_geo.prediction.training import FittedRidge, predict_ridge


def test_error_band_requires_30():
    assert error_band_amplitude([1.0] * 29) is None

    errors = list(range(30))
    amplitude = error_band_amplitude(errors)
    assert amplitude is not None
    expected = float(np.percentile(np.abs(np.asarray(errors, dtype=np.float64)), 90.0))
    assert amplitude == pytest.approx(expected)


def test_band_label_is_historical_not_confidence():
    label = risk_mod.ERROR_BAND_LABEL
    assert "90% confidence" not in label
    assert "historical" in label.lower()


def test_risk_unstable_crosses_threshold():
    assert is_risk_unstable(35.0, 45.0) is True  # crosses 40
    assert is_risk_unstable(45.0, 55.0) is True  # crosses 50
    assert is_risk_unstable(30.0, 35.0) is False
    assert is_risk_unstable(55.0, 60.0) is False
    assert is_risk_unstable(40.0, 40.0) is False
    assert is_risk_unstable(None, None) is False


def test_risk_band_clips_0_100():
    assert risk_band(95.0, 10.0) == (85.0, 100.0)
    assert risk_band(5.0, 10.0) == (0.0, 15.0)
    assert risk_band(None, 10.0) == (None, None)
    assert risk_band(50.0, None) == (None, None)


def test_clip_frequency_recorded():
    fitted = FittedRidge(
        intercept=150.0,
        coefficients=(0.0,) * 6,
        scaler_mean=(0.0,) * 6,
        scaler_scale=(1.0,) * 6,
        feature_order=FEATURE_ORDER,
    )
    row = ExampleRow(
        municipality_code="001",
        municipality_name="M",
        target_year=2027,
        target=None,
        target_known_count=0,
        features={f: 0.0 for f in FEATURE_ORDER},
        origins={f: None for f in FEATURE_ORDER},
    )
    ds = FeatureDataset(2027, [row], (), FEATURE_ORDER)

    raw, clipped = predict_ridge(fitted, ds)
    assert clipped[0] == 100.0
    assert int(np.count_nonzero(raw != clipped)) == 1
