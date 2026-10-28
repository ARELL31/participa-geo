from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = REPO_ROOT / "data/processed/national/continuity"


def _rows(name: str) -> list[dict[str, str]]:
    with (ARTIFACTS / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


pytestmark = pytest.mark.skipif(
    not (ARTIFACTS / "coverage-report.csv").is_file(),
    reason="requires the local real-data continuity audit artifacts",
)


def test_official_2023_reference_is_exact_on_common_ccpc_and_mgs_sections():
    report = json.loads((ARTIFACTS / "continuity-build.json").read_text(encoding="utf-8"))

    assert report["plan_reference_column"] == "Nueva_Dttacion_2023"
    assert report["reference_common_count"] == 70_301
    assert report["reference_ccpc_mismatches"] == 0
    assert report["reference_mgs_mismatches"] == 0
    assert report["national_coverage_by_year"]["2024"] < 0.98
    assert report["national_status_by_year"]["2024"] == "insufficient"
    assert report["ccpc_2024_without_mgs_count"] == 450
    assert report["mgs_without_ccpc_2024_count"] == 2_967


def test_official_2018_and_2021_links_are_tagged_only_as_derfe2023():
    for year in (2018, 2021):
        rows = _rows(f"section-continuity-{year}.csv")
        matched = [row for row in rows if row["status"] == "matched"]
        assert matched
        assert all(row["target_district"] for row in matched)
        assert any("Distrito_PEF" + str(year) in row["evidence"] for row in matched)
        assert all(
            not row["target_section"] and not row["target_district"]
            for row in rows
            if row["status"] == "unmatched"
        )


def test_real_historical_coverage_gates_fail_closed():
    rows = _rows("coverage-report.csv")
    national = {int(row["year"]): row for row in rows if row["district_code"] == "ALL"}
    for year in (2009, 2012, 2015, 2018, 2021):
        assert float(national[year]["coverage"]) < 0.98
        assert national[year]["status"] == "insufficient"
        district_rows = [
            row for row in rows if int(row["year"]) == year and row["district_code"] != "ALL"
        ]
        assert all(row["status"] == "insufficient" for row in district_rows)


def test_2024_coverage_counts_ccpc_without_mgs_as_uncovered_and_mgs_only_without_ln():
    rows = _rows("coverage-report.csv")
    national = next(row for row in rows if row["year"] == "2024" and row["district_code"] == "ALL")

    assert float(national["coverage"]) < 0.98
    assert national["status"] == "insufficient"
    assert int(national["ccpc_without_mgs_section_count"]) == 450
    assert int(national["ccpc_without_mgs_ln"]) > 0
    assert int(national["mgs_only_section_count"]) == 2_967
    assert int(national["mgs_only_ln"]) == 0
    assert int(national["section_universe_gap_count"]) == 3_417
    assert int(national["unmatched_ccpc_section_count"]) == 450
    assert int(national["unmatched_ccpc_ln"]) == int(national["reference_ln"]) - int(
        national["matched_ln"]
    )
    mgs_only = _rows("mgs-sections-without-2024-ccpc.csv")
    assert len(mgs_only) == 2_967
    assert all(row["status"] == "uncovered_no_ccpc_ln" for row in mgs_only)
    assert all(row["section_count"] == "1" and row["ln"] == "" for row in mgs_only)
    assert all(row["ln_status"] == "absent_no_ccpc_fact" for row in mgs_only)


def test_new_seven_district_numbers_do_not_inherit_historical_identity():
    new_keys = {
        ("02", "09"),
        ("05", "08"),
        ("19", "13"),
        ("19", "14"),
        ("21", "16"),
        ("22", "06"),
        ("31", "06"),
    }
    rows = _rows("coverage-report.csv")
    actual = {
        (row["state_code"], row["district_code"]): row
        for row in rows
        if row["year"] == "2021" and row["district_code"] != "ALL"
    }
    assert all(actual[key]["status"] == "insufficient" for key in new_keys)


def test_mgs_bridge_preserves_2581_pairs_and_72_split_municipalities():
    pairs = _rows("bridge-municipality-district.csv")
    splits = {
        (row["state_code"], row["municipality_code"])
        for row in pairs
        if row["is_split"].lower() == "true"
    }
    assert len(pairs) == 2_581
    assert len(splits) == 72


def test_intersection_aggregates_reconcile_counts_and_plan():
    aggregates = _rows("agg-municipality-district-year.csv")
    districts = _rows("district-observations.csv")
    assert aggregates
    assert all(row["district_plan"] == "DERFE2023" for row in aggregates)
    assert all(
        int(row["ln"]) == int(row["sv"]) + int(row["nv"]) + int(row["ns"]) for row in aggregates
    )
    for year in (2009, 2012, 2015, 2018, 2021):
        aggregate_rows = [row for row in aggregates if int(row["year"]) == year]
        district_rows = [row for row in districts if int(row["year"]) == year]
        assert sum(int(row["ln"]) for row in aggregate_rows) == sum(
            int(row["ln"]) for row in district_rows
        )
