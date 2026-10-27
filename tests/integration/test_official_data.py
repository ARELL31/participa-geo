"""Integration tests over the verified official CCPC data for Jalisco.

These tests read the aggregated artifacts in ``data/processed`` and the source
manifests in ``data/sources.json``, cross-checking them against the audited
evidence in ``docs/methodology/evidence/jalisco-audit.json``. They require the
``./data`` and ``./docs`` mounts on the ``api`` service (see ``compose.yaml``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from participa_geo.ingestion.pipeline import run_ingest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw" / "ccpc"
PROCESSED = REPO_ROOT / "data" / "processed"
EVIDENCE = REPO_ROOT / "docs" / "methodology" / "evidence" / "jalisco-audit.json"
SOURCES = REPO_ROOT / "data" / "sources.json"

YEARS = [2009, 2012, 2015, 2018, 2021, 2024]


def _audit() -> dict[int, dict]:
    return {entry["year"]: entry for entry in json.loads(EVIDENCE.read_text())}


def _parquet() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "municipal-observations.parquet")


def test_official_observations_count_and_municipalities():
    frame = _parquet()
    assert len(frame) == 750
    for year in YEARS:
        subset = frame[frame["year"] == year]
        assert subset["municipality_code"].nunique() == 125, year


def test_official_totals_match_evidence():
    audit = _audit()
    frame = _parquet()
    for year, group in frame.groupby("year"):
        evidence = audit[int(year)]
        assert int(group["ln"].sum()) == evidence["totals"]["LN"], year
        assert int(group["sv"].sum()) == evidence["totals"]["SV"], year
        assert int(group["nv"].sum()) == evidence["totals"]["NV"], year
        assert int(group["ns"].sum()) == evidence["totals"]["NS"], year


def test_official_source_rows_total_2999641():
    provenance = json.loads((PROCESSED / "provenance.json").read_text())
    assert sum(source["source_row_count"] for source in provenance["sources"]) == 2999641


def test_2024_blank_del_count_is_2953():
    provenance = json.loads((PROCESSED / "provenance.json").read_text())
    by_year = {source["year"]: source for source in provenance["sources"]}
    assert by_year[2024]["blank_del_count"] == 2953
    # The audit reports no blank DEF in 2024.
    assert by_year[2024]["blank_def_count"] == 0


def test_official_sha256_match_sources_manifest():
    audit = _audit()
    manifest = {s["year"]: s for s in json.loads(SOURCES.read_text())["sources"]}
    for year in YEARS:
        assert manifest[year]["sha256"] == audit[year]["sha256"], year
        assert manifest[year]["member"] == audit[year]["member"], year
        assert manifest[year]["source_url"] == audit[year]["source"], year


def test_reingest_same_hash_no_duplicates(tmp_path):
    """Re-running ingestion yields identical aggregates/hash and no duplicate keys."""
    out_one = tmp_path / "one"
    out_two = tmp_path / "two"
    result_one = run_ingest(DATA_RAW, out_one, sources=SOURCES)
    result_two = run_ingest(DATA_RAW, out_two, sources=SOURCES)

    assert result_one.aggregate_sha256 == result_two.aggregate_sha256
    assert result_one.observation_count == 750
    assert result_two.observation_count == 750

    frame_one = pd.read_parquet(out_one / "municipal-observations.parquet")
    frame_two = pd.read_parquet(out_two / "municipal-observations.parquet")
    pd.testing.assert_frame_equal(frame_one, frame_two)

    # No duplicate (year, municipality) keys across the re-ingested output.
    assert frame_one.duplicated(subset=["year", "municipality_code"]).sum() == 0
    assert len(frame_one) == 750
