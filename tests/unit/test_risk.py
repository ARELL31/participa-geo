"""Unit tests for the analytical traffic-light risk classification.

The thresholds are normative (Spec §8), never learned: low <40, medium 40-<50,
high >=50, and insufficient when a municipality is not eligible or its estimate
is unknown. An unknown value must never be stored or classified as zero.
"""

from __future__ import annotations

from participa_geo.prediction.risk import classify_risk


def test_risk_boundaries():
    assert classify_risk(39.999, eligible=True) == "low"
    assert classify_risk(40.0, eligible=True) == "medium"
    assert classify_risk(49.999, eligible=True) == "medium"
    assert classify_risk(50.0, eligible=True) == "high"
    assert classify_risk(None, eligible=False) == "insufficient"


def test_unknown_quality_never_becomes_zero():
    # A missing estimate is "insufficient", never a numeric zero.
    assert classify_risk(None, eligible=True) == "insufficient"
    assert classify_risk(None, eligible=False) == "insufficient"
    # An ineligible municipality with a nominal value is still insufficient.
    assert classify_risk(0.0, eligible=False) == "insufficient"
