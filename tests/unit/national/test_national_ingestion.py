from __future__ import annotations

import csv
import zipfile
from pathlib import Path

import pytest

from participa_geo.ingestion.national import (
    _atomic_json,
    aggregate_national_municipal,
    read_national_ccpc,
)
from participa_geo.ingestion.schema import CCPC_COLUMNS, CCPCSchemaError
from participa_geo.ingestion.section_fact import SectionFact


def make_zip(tmp_path: Path, rows: list[list[str]], year: int = 2009) -> Path:
    archive = tmp_path / f"ccpc-{year}.zip"
    member = f"source/{year}_oax.csv"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        with zipped.open(member, "w") as binary:
            import io
            text = io.TextIOWrapper(binary, encoding="utf-8", newline="")
            writer = csv.writer(text)
            writer.writerow(CCPC_COLUMNS)
            writer.writerows(rows)
            text.flush()
        for index in range(31):
            with zipped.open(f"source/{year}_{index:02d}.csv", "w") as binary:
                import io
                text = io.TextIOWrapper(binary, encoding="utf-8", newline="")
                csv.writer(text).writerow(CCPC_COLUMNS)
                text.flush()
    return archive


def row(
    *,
    year="2009",
    state="20",
    municipality="549",
    name='H VILLA TEZOATLAN, "SEGURA Y LUNA"',
    def_code="3",
    ln="10",
    sv="7",
    nv="2",
    ns="1",
    age="25",
    sex="0",
) -> list[str]:
    return [
        year,
        "05/07/2009",
        state,
        "OAXACA",
        municipality,
        name,
        "1",
        "R",
        def_code,
        "1",
        sex,
        age,
        ln,
        sv,
        nv,
        ns,
    ]


def test_parser_handles_oaxaca_quoted_comma_and_normalizes_codes(tmp_path: Path) -> None:
    archive = make_zip(tmp_path, [row()])

    fact = next(read_national_ccpc(archive, 2009))

    assert isinstance(fact, SectionFact)
    assert fact.municipality_name == 'H VILLA TEZOATLAN, "SEGURA Y LUNA"'
    assert (fact.state_code, fact.municipality_code, fact.district_2021) == ("20", "549", "03")


def test_blank_def_remains_null_for_2009(tmp_path: Path) -> None:
    archive = make_zip(tmp_path, [row(def_code=" ")])

    fact = next(read_national_ccpc(archive, 2009))

    assert fact.district_2021 is None
    assert fact.district_2023 is None
    assert fact.source_district == " "


def test_state_municipality_and_def_codes_are_zero_padded(tmp_path: Path) -> None:
    archive = make_zip(tmp_path, [row(state="1", municipality="1", def_code="3")])

    fact = next(read_national_ccpc(archive, 2009))

    assert (fact.state_code, fact.municipality_code, fact.district_2021) == (
        "01",
        "001",
        "03",
    )


def test_2024_def_uses_2023_plan(tmp_path: Path) -> None:
    archive = make_zip(tmp_path, [row(year="2024", def_code="3")], 2024)

    fact = next(read_national_ccpc(archive, 2024))

    assert fact.district_2021 is None
    assert fact.district_2023 == "03"


def test_reconciliation_mismatch_fails(tmp_path: Path) -> None:
    archive = make_zip(tmp_path, [row(ln="11")])

    with pytest.raises(CCPCSchemaError, match="LN=11"):
        list(read_national_ccpc(archive, 2009))


def test_duplicate_analytical_key_fails(tmp_path: Path) -> None:
    archive = make_zip(tmp_path, [row(), row()])

    with pytest.raises(CCPCSchemaError, match="duplicate"):
        list(read_national_ccpc(archive, 2009))


def test_municipal_aggregation_sums_counts_and_ln_shares() -> None:
    first = SectionFact(
        2009, "20", "549", "1", "03", None, "0", 25, "R", "OAXACA", "TEZOATLAN",
        10, 7, 2, 1, "hash", 2,
    )
    second = SectionFact(
        2009, "20", "549", "2", "03", None, "1", 65, "U", "OAXACA", "TEZOATLAN",
        20, 12, 6, 2, "hash", 3,
    )

    aggregate = aggregate_national_municipal([first, second])[0]

    assert (aggregate.ln, aggregate.sv, aggregate.nv, aggregate.ns) == (30, 19, 8, 3)
    assert aggregate.young_share == pytest.approx(1 / 3)
    assert aggregate.senior_share == pytest.approx(2 / 3)
    assert aggregate.rural_share == pytest.approx(1 / 3)
    assert aggregate.municipality_name == "TEZOATLAN"


def test_municipal_quality_thresholds_preserve_insufficient_observations() -> None:
    adequate = SectionFact(
        2009, "20", "549", "1", "03", None, "0", 25, "U", "OAXACA", "TEZOATLAN",
        1120, 900, 108, 112, "hash", 2,
    )
    low_known = SectionFact(
        2009, "20", "550", "1", "03", None, "0", 25, "U", "OAXACA", "HUAJUAPAN",
        999, 900, 99, 0, "hash", 3,
    )

    by_municipality = {
        observation.municipality_code: observation
        for observation in aggregate_national_municipal([adequate, low_known])
    }

    assert by_municipality["549"].eligible is True
    assert by_municipality["550"].eligible is False
    assert by_municipality["550"].quality_reasons == ("insufficient_known_votes",)


def test_atomic_manifest_is_readable_by_group_and_other_users(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"

    _atomic_json(output, {"ok": True})

    assert output.stat().st_mode & 0o777 == 0o644
