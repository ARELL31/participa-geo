"""Integration tests for the ``Repository`` read interfaces.

These exercise ``get_territories`` and ``get_history`` against the migrated and
loaded test database: pagination bounds, stable numeric ordering, ``q`` search
escaping, and the state-vs-territory aggregation (which must sum counts before
recomputing rates).
"""

from __future__ import annotations

from participa_geo.db.repository import Repository

#: State totals from docs/methodology/evidence/jalisco-audit.json (2009).
EVIDENCE_2009 = {"ln": 5133870, "sv": 2570273, "nv": 2450936, "ns": 112661}
EVIDENCE_2009_ABSTENTION_PCT = 48.811670655413864


def _repo(session):
    return Repository(session)


def test_get_territories_default_page_and_order(postgis_session):
    records, total = _repo(postgis_session).get_territories(
        state_code="14", q=None, page=1, page_size=25
    )
    assert total == 125
    assert len(records) == 25
    codes = [r.municipality_code for r in records]
    # Stable numeric order (zero-padded 3-digit INE code).
    assert codes == sorted(codes)
    assert codes == [f"{i:03d}" for i in range(1, 26)]


def test_get_territories_pagination_bounds(postgis_session):
    repo = _repo(postgis_session)
    page1, total = repo.get_territories(state_code="14", q=None, page=1, page_size=125)
    assert total == 125 and len(page1) == 125

    page2, total2 = repo.get_territories(state_code="14", q=None, page=2, page_size=100)
    assert total2 == 125
    assert len(page2) == 25
    assert page2[0].municipality_code == "101"
    assert page2[-1].municipality_code == "125"

    page3, _ = repo.get_territories(state_code="14", q=None, page=3, page_size=100)
    assert page3 == []


def test_get_territories_q_escaping_literal_wildcards(postgis_session):
    repo = _repo(postgis_session)
    # `%`, `_` and `!` are escaped to literals, not LIKE wildcards.
    for q in ("%", "_", "!"):
        records, total = repo.get_territories(state_code="14", q=q, page=1, page_size=25)
        assert total == 0, q
        assert records == [], q


def test_get_territories_q_substring_and_code(postgis_session):
    repo = _repo(postgis_session)
    records, total = repo.get_territories(
        state_code="14", q="Guadalajara", page=1, page_size=25
    )
    assert total == 1
    assert records[0].name == "GUADALAJARA"

    by_code, total_code = repo.get_territories(
        state_code="14", q="001", page=1, page_size=25
    )
    assert total_code == 1
    assert by_code[0].municipality_code == "001"


def test_get_history_territory_sums_and_order(postgis_session):
    repo = _repo(postgis_session)
    territories, _ = repo.get_territories(state_code="14", q=None, page=1, page_size=1)
    territory = territories[0]  # 001 (ACATIC)

    records, total = repo.get_history(
        territory_id=territory.id, year=None, page=1, page_size=10
    )
    assert total == 6
    assert [r.year for r in records] == [2009, 2012, 2015, 2018, 2021, 2024]
    for record in records:
        assert record.ln == record.sv + record.nv + record.ns
        assert record.territory_id == territory.id


def test_get_history_territory_pagination(postgis_session):
    repo = _repo(postgis_session)
    territories, _ = repo.get_territories(state_code="14", q=None, page=1, page_size=1)
    page1, total = repo.get_history(
        territory_id=territories[0].id, year=None, page=1, page_size=2
    )
    assert total == 6
    assert [r.year for r in page1] == [2009, 2012]
    page3, _ = repo.get_history(
        territory_id=territories[0].id, year=None, page=3, page_size=2
    )
    assert [r.year for r in page3] == [2021, 2024]


def test_get_history_year_filter(postgis_session):
    repo = _repo(postgis_session)
    territories, _ = repo.get_territories(state_code="14", q=None, page=1, page_size=1)
    records, total = repo.get_history(
        territory_id=territories[0].id, year=2024, page=1, page_size=10
    )
    assert total == 1 and records[0].year == 2024

    state, stotal = repo.get_history(
        territory_id=None, year=2024, page=1, page_size=10
    )
    assert stotal == 1 and state[0].year == 2024


def test_get_history_state_sums_counts_before_rates(postgis_session):
    repo = _repo(postgis_session)
    records, total = repo.get_history(territory_id=None, year=None, page=1, page_size=10)
    assert total == 6
    by_year = {r.year: r for r in records}

    # 2009 state counts are summed from the 125 municipalities.
    assert by_year[2009].ln == EVIDENCE_2009["ln"]
    assert by_year[2009].sv == EVIDENCE_2009["sv"]
    assert by_year[2009].nv == EVIDENCE_2009["nv"]
    assert by_year[2009].ns == EVIDENCE_2009["ns"]
    # Abstention recomputed from sums (100 * NV / (SV + NV)), never averaged.
    assert abs(by_year[2009].abstention_pct - EVIDENCE_2009_ABSTENTION_PCT) < 1e-6
    assert abs(by_year[2009].participation_pct - (100 - EVIDENCE_2009_ABSTENTION_PCT)) < 1e-6
    # All six state rows carry the known LN totals.
    assert {r.year: r.ln for r in records} == {
        2009: 5133870,
        2012: 5027267,
        2015: 5513033,
        2018: 5904226,
        2021: 6214764,
        2024: 6619379,
    }
