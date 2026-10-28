from __future__ import annotations

from uuid import UUID

import pytest

from participa_geo.ingestion.schema import MunicipalityKey, MunicipalObservation
from pipelines.validation.identity_national import (
    NationalIdentityError,
    build_national_municipal_identity,
)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, references):
        self.references = references
        self.writes = []

    def execute(self, statement, params=None):
        sql = str(statement)
        if sql.lstrip().startswith("SELECT state_code, municipality_code, name"):
            return _Result(self.references)
        self.writes.append((sql, params))
        return _Result([])


def _reference_rows():
    return [
        (
            f"{state:02d}",
            f"{municipality:03d}",
            f"MGS {state}-{municipality}",
            b"wkb",
            4326,
            "INE MGS 15-DIC-2025",
        )
        for state in range(1, 33)
        for municipality in range(1, 79 if state <= 13 else 78)
    ]


def _obs(state, code, year):
    return MunicipalObservation(
        key=MunicipalityKey(state, code),
        year=year,
        ln=1200,
        sv=800,
        nv=300,
        ns=100,
        municipality_name="possibly truncated",
        young_share=0.2,
        senior_share=0.1,
        rural_share=0.3,
        source_version_id=UUID(int=year),
    )


def test_national_identity_builder_writes_all_2477_mgs_references_idempotently():
    refs = _reference_rows()
    session = _Session(refs)
    observations = [_obs("01", "001", year) for year in (2009, 2015, 2018, 2021, 2024)]

    first = build_national_municipal_identity(session, observations)
    first_writes = list(session.writes)
    second = build_national_municipal_identity(session, observations)

    assert first.reference_count == 2477
    assert first.origin_count == 5
    assert first.verified_count == 5
    assert second == first
    assert session.writes == first_writes + first_writes
    refs_written = [
        params for sql, params in first_writes if "INSERT INTO territory_version" in sql
    ]
    national_refs = [params for params in refs_written if params.get("reference_date")]
    assert len(national_refs) == 2477
    assert all(params["source_srid"] == 4326 for params in national_refs)


def test_national_identity_builder_preserves_missing_2012_and_marks_unmatched_ambiguous():
    session = _Session(_reference_rows())
    observations = [
        _obs("01", "001", 2009),
        _obs("01", "001", 2015),
        _obs("01", "001", 2018),
        _obs("01", "001", 2021),
        _obs("01", "001", 2024),
        _obs("01", "999", 2009),
    ]

    report = build_national_municipal_identity(session, observations)

    assert report.origin_count == 6
    assert report.verified_count == 5
    assert report.ambiguous_count == 1
    assert not any(params.get("origin_year") == 2012 for _, params in session.writes)
    correspondences = [
        params for sql, params in session.writes if "INSERT INTO territory_correspondence" in sql
    ]
    unmatched = next(row for row in correspondences if row["identity_status"] == "ambiguous")
    assert unmatched["reference_id"] is None
    assert unmatched["footprint_status"] == "not_verified"


def test_duplicate_mgs_entity_municipality_key_fails_closed():
    refs = _reference_rows()
    refs.append(refs[0])
    session = _Session(refs)

    with pytest.raises(NationalIdentityError, match="duplicate"):
        build_national_municipal_identity(session, [_obs("01", "001", 2024)])


def test_municipal_code_is_resolved_with_entity_and_not_name():
    session = _Session(_reference_rows())

    audit = build_national_municipal_identity(
        session,
        [_obs("01", "001", 2024), _obs("02", "001", 2024)],
    )

    assert audit.verified_count == 2
    assert audit.ambiguous_count == 0
