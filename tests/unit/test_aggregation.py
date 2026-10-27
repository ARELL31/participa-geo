"""Unit tests for municipal aggregation of CCPC rows.

Rates are computed from summed counts, never from the mean of per-row rates.
Demographic shares (young/senior/rural) use ``LN`` as denominator, never ``SV``.
"""

from __future__ import annotations

import pytest

from participa_geo.indicators.calculations import calculate_indicators
from participa_geo.ingestion.aggregate import aggregate_municipal
from participa_geo.ingestion.schema import CCPCRow


def _row(
    municipality_code: str = "1",
    year: int = 2024,
    ln: int = 100,
    sv: int = 40,
    nv: int = 40,
    ns: int = 20,
    age: int = 30,
    section_type: str = "U",
    section: str = "1",
) -> CCPCRow:
    return CCPCRow(
        year=year,
        election_date="2/6/2024",
        state_code="14",
        state_name="JALISCO",
        municipality_code=municipality_code,
        municipality_name="Acatic",
        section=section,
        section_type=section_type,
        federal_district=1,
        local_district=2,
        sex=0,
        age=age,
        ln=ln,
        sv=sv,
        nv=nv,
        ns=ns,
    )


def test_aggregates_counts_not_mean_rates():
    rows = [
        _row(section="1", ln=100, sv=90, nv=10, ns=0),
        _row(section="2", ln=10, sv=1, nv=9, ns=0),
    ]
    observations = aggregate_municipal(rows)
    assert len(observations) == 1
    obs = observations[0]
    assert obs.sv == 91
    assert obs.nv == 19
    assert obs.ln == 110
    result = calculate_indicators(obs.ln, obs.sv, obs.nv, obs.ns)
    # (90+1)/(100+10)*100, not (90/100 + 1/10)/2.
    assert result.participation_pct == pytest.approx(91 / 110 * 100)
    assert result.participation_pct != pytest.approx(50.0)


def test_shares_use_ln_denominator():
    rows = [
        _row(section="1", ln=100, sv=60, nv=40, ns=0, age=20, section_type="U"),
        _row(section="2", ln=50, sv=30, nv=20, ns=0, age=65, section_type="R"),
        _row(section="3", ln=50, sv=25, nv=25, ns=0, age=40, section_type="M"),
    ]
    obs = aggregate_municipal(rows)[0]
    assert obs.ln == 200
    # young 18-29 -> 100/200; senior 60+ -> 50/200; rural R -> 50/200.
    assert obs.young_share == pytest.approx(0.5)
    assert obs.senior_share == pytest.approx(0.25)
    assert obs.rural_share == pytest.approx(0.25)


def test_senior_includes_ages_above_100():
    # Ages above 100 stay raw in the row and are still senior (>= 60).
    rows = [
        _row(section="1", ln=100, sv=60, nv=40, ns=0, age=130, section_type="U"),
    ]
    obs = aggregate_municipal(rows)[0]
    assert obs.senior_share == pytest.approx(1.0)
    assert obs.young_share == pytest.approx(0.0)


def test_municipalities_grouped_separately():
    rows = [
        _row(municipality_code="1", section="1", ln=100, sv=50, nv=50, ns=0),
        _row(municipality_code="2", section="1", ln=300, sv=150, nv=150, ns=0),
    ]
    observations = aggregate_municipal(rows)
    assert len(observations) == 2
    by_code = {o.key.municipality_code: o for o in observations}
    assert by_code["001"].ln == 100
    assert by_code["002"].ln == 300


def test_municipality_code_normalized_to_3_digits():
    rows = [_row(municipality_code="1", section="1", ln=100, sv=50, nv=50, ns=0)]
    obs = aggregate_municipal(rows)[0]
    assert obs.key.municipality_code == "001"
    assert obs.key.state_code == "14"
