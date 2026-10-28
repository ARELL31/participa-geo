from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from participa_geo.ingestion.national import ingest_national, resolve_current_generation
from participa_geo.ingestion.schema import CCPC_COLUMNS, CCPCSchemaError

YEARS = (2009, 2012, 2015, 2018, 2021, 2024)


def make_national_sources(
    root: Path,
    *,
    version: str = "first",
    bad_year: int | None = None,
    repeated_state: bool = False,
    hash_override_year: int | None = None,
) -> tuple[Path, Path]:
    source_dir = root / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    sources = []
    for year in YEARS:
        archive_path = source_dir / f"ccpc-{year}.zip"
        members = []
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for state in range(1, 33):
                member = f"INE/{year}/state-{state:02d}.csv"
                members.append(member)
                state_value = 1 if repeated_state and state == 32 else state
                values = [
                    str(year), "05/07/2009", str(state_value), f"STATE {state:02d}",
                    "1", f"MUNICIPALITY {version}", "1", "U", "1", "1", "0", "25",
                    "1100", "900", "100", "100",
                ]
                if year == bad_year and state == 1:
                    values[12] = "1101"
                with archive.open(member, "w") as binary:
                    import io

                    text = io.TextIOWrapper(binary, encoding="utf-8", newline="")
                    writer = csv.writer(text)
                    writer.writerow(CCPC_COLUMNS)
                    writer.writerow(values)
                    text.flush()
        archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        sources.append(
            {
                "year": year,
                "source_url": f"https://example.invalid/ccpc-{year}.zip",
                "last_modified": "2026-10-27",
                "retrieved_at": "2026-10-27",
                "zip": archive_path.name,
                "sha256": "0" * 64 if year == hash_override_year else archive_hash,
                "members": members,
            }
        )
    inventory = root / "sources-national.json"
    inventory.write_text(json.dumps({"years": list(YEARS), "sources": sources}))
    return source_dir, inventory


def test_complete_generation_switches_pointer_and_records_all_artifact_hashes(
    tmp_path: Path,
) -> None:
    source_dir, inventory = make_national_sources(tmp_path)
    output_dir = tmp_path / "processed"

    first = ingest_national(source_dir, output_dir, sources_path=inventory)
    first_pointer = json.loads((output_dir / "current.json").read_text())
    first_dir = resolve_current_generation(output_dir)
    source_dir, inventory = make_national_sources(tmp_path, version="second")
    second = ingest_national(source_dir, output_dir, sources_path=inventory)
    second_pointer = json.loads((output_dir / "current.json").read_text())
    second_dir = resolve_current_generation(output_dir)

    assert first.generation_id != second.generation_id
    assert first_pointer["generation_id"] != second_pointer["generation_id"]
    assert first_dir != second_dir
    assert first_dir.is_dir() and second_dir.is_dir()
    expected = {
        *(f"ccpc-section-{year}.parquet" for year in YEARS),
        "municipal-observations.csv",
        "municipal-observations.parquet",
        "national-ingest.json",
    }
    assert expected <= {path.name for path in second_dir.iterdir()}
    manifest = json.loads((second_dir / "national-ingest.json").read_text())
    for name, artifact in manifest["artifacts"].items():
        assert hashlib.sha256((second_dir / name).read_bytes()).hexdigest() == artifact["sha256"]
    assert manifest["municipality_count"] == 32
    assert len(manifest["sources"][0]["csv_members"]) == 32
    assert len({member["state_code"] for member in manifest["sources"][0]["csv_members"]}) == 32


def test_failed_generation_keeps_previous_pointer_and_files(tmp_path: Path) -> None:
    source_dir, inventory = make_national_sources(tmp_path)
    output_dir = tmp_path / "processed"
    ingest_national(source_dir, output_dir, sources_path=inventory)
    old_pointer = (output_dir / "current.json").read_bytes()
    old_generation = resolve_current_generation(output_dir)
    source_dir, inventory = make_national_sources(tmp_path, version="bad", bad_year=2009)

    with pytest.raises(CCPCSchemaError, match="LN=1101"):
        ingest_national(source_dir, output_dir, sources_path=inventory)

    assert (output_dir / "current.json").read_bytes() == old_pointer
    assert resolve_current_generation(output_dir) == old_generation
    assert (old_generation / "national-ingest.json").is_file()


def test_source_zip_sha_mismatch_fails_before_publishing(tmp_path: Path) -> None:
    source_dir, inventory = make_national_sources(tmp_path, hash_override_year=2009)
    output_dir = tmp_path / "processed"

    with pytest.raises(CCPCSchemaError, match="SHA-256 mismatch"):
        ingest_national(source_dir, output_dir, sources_path=inventory)

    assert not (output_dir / "current.json").exists()


def test_source_inventory_member_mismatch_fails_before_publishing(tmp_path: Path) -> None:
    source_dir, inventory = make_national_sources(tmp_path)
    declared = json.loads(inventory.read_text())
    declared["sources"][0]["members"][0] = "INE/2009/not-the-archive-member.csv"
    inventory.write_text(json.dumps(declared))
    output_dir = tmp_path / "processed"

    with pytest.raises(CCPCSchemaError, match="member names/count differ"):
        ingest_national(source_dir, output_dir, sources_path=inventory)

    assert not (output_dir / "current.json").exists()


def test_duplicate_edocve_across_csv_members_fails(tmp_path: Path) -> None:
    source_dir, inventory = make_national_sources(tmp_path, repeated_state=True)
    output_dir = tmp_path / "processed"

    with pytest.raises(CCPCSchemaError, match="distinct EDOCVE"):
        ingest_national(source_dir, output_dir, sources_path=inventory)

    assert not (output_dir / "current.json").exists()
