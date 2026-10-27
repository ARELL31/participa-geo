"""Unit tests for participation indicators and quality decisions.

The exact boundary values are fixed by the approved design (Spec §6) and the task
brief: ``unknown_share`` is a fraction 0–1 while the API rates are percentage
points 0–100. ``NS`` is never reclassified as abstention.
"""

from __future__ import annotations

import pytest
from participa_geo.indicators.calculations import (
    assess_quality,
    calculate_indicators,
)
from participa_geo.ingestion.schema import MunicipalityKey, MunicipalObservation


def test_ns_is_not_abstention():
    result = calculate_indicators(ln=100, sv=40, nv=40, ns=20)
    assert result.participation_pct == 50.0
    assert result.abstention_pct == 50.0
    assert result.unknown_share == 0.20
    assert (result.ns_lower_pct, result.ns_upper_pct) == (40.0, 60.0)


def test_zero_denominator_is_null():
    result = calculate_indicators(ln=0, sv=0, nv=0, ns=0)
    assert result.participation_pct is None
    assert result.abstention_pct is None
    assert result.unknown_share is None
    assert result.ns_lower_pct is None
    assert result.ns_upper_pct is None


def test_unknown_share_is_fraction_not_percentage():
    result = calculate_indicators(ln=1000, sv=450, nv=450, ns=100)
    assert result.unknown_share == pytest.approx(0.10)
    assert result.abstention_pct == pytest.approx(50.0)
    assert result.ns_lower_pct == pytest.approx(45.0)
    assert result.ns_upper_pct == pytest.approx(55.0)


def test_abstention_denominator_excludes_ns():
    # NS does not enlarge the known denominator used for participation/abstention.
    result = calculate_indicators(ln=1000, sv=400, nv=400, ns=200)
    assert result.participation_pct == pytest.approx(50.0)
    assert result.abstention_pct == pytest.approx(50.0)


def _observation(ln: int, sv: int, nv: int, ns: int) -> MunicipalObservation:
    return MunicipalObservation(
        key=MunicipalityKey(state_code="14", municipality_code="001"),
        year=2024,
        ln=ln,
        sv=sv,
        nv=nv,
        ns=ns,
        municipality_name="Acatic",
    )


def test_quality_boundary():
    # 10% unknown, 1800 known -> eligible.
    assert assess_quality(_observation(2000, 900, 900, 200)).eligible is True
    # Just above the 10% unknown ceiling -> rejected.
    assert assess_quality(_observation(2000, 899, 900, 201)).eligible is False
    # Known count below 1000 -> rejected even with zero NS.
    assert assess_quality(_observation(999, 500, 499, 0)).eligible is False


def test_quality_reasons_are_stable():
    eligible = assess_quality(_observation(2000, 900, 900, 200))
    assert eligible.reasons == []
    assert eligible.identity_status is None
    assert eligible.footprint_status is None

    high_unknown = assess_quality(_observation(2000, 899, 900, 201))
    assert high_unknown.reasons == ["high_unknown_share"]

    small = assess_quality(_observation(999, 500, 499, 0))
    assert small.reasons == ["small_known_count"]


def test_quality_invalid_counts_flagged():
    # Accounting identity LN = SV + NV + NS is enforced.
    bad = assess_quality(_observation(1000, 400, 400, 100))
    assert bad.eligible is False
    assert bad.reasons == ["invalid_counts"]

    negative = assess_quality(_observation(1000, -1, 400, 601))
    assert negative.eligible is False
    assert negative.reasons == ["invalid_counts"]


def test_quality_zero_denominator_flagged():
    decision = assess_quality(_observation(0, 0, 0, 0))
    assert decision.eligible is False
    assert decision.reasons == ["zero_denominator"]
