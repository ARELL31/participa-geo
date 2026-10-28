"""Streaming ingestion of national INE CCPC ZIP archives."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import stat
import tempfile
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from participa_geo.ingestion.schema import CCPC_COLUMNS, CCPCSchemaError, normalize_code
from participa_geo.ingestion.section_fact import NationalMunicipalObservation, SectionFact

NATIONAL_YEARS = (2009, 2012, 2015, 2018, 2021, 2024)
NATIONAL_ZIP_URLS = {
    2009: "https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2009.zip",
    2012: "https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2012.zip",
    2015: "https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2015.zip",
    2018: "https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2018.zip",
    2021: "https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2021.zip",
    2024: "https://ine.mx/wp-content/uploads/2025/08/DatosAbiertos_DECEyEC_ConteosCensales2024.zip",
}
_FIELDS = {name: index for index, name in enumerate(CCPC_COLUMNS)}


def _sha256_member(archive: zipfile.ZipFile, member: str) -> str:
    digest = hashlib.sha256()
    with archive.open(member) as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integer(raw: str, field: str, member: str, row_number: int, *, nullable=False):
    value = raw.strip()
    if nullable and not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise CCPCSchemaError(
            f"{member}: row {row_number}: {field} must be an integer, got {raw!r}"
        ) from None


def _row_key(values: list[str], member: str, row_number: int) -> int:
    municipality = _integer(values[_FIELDS["MPIOCVE"]], "MPIOCVE", member, row_number)
    section = _integer(values[_FIELDS["SECCION"]], "SECCION", member, row_number)
    sex = _integer(values[_FIELDS["SEXO"]], "SEXO", member, row_number)
    age = _integer(values[_FIELDS["EDAD"]], "EDAD", member, row_number)
    return (((municipality * 100_000 + section) * 10 + sex) * 256) + age


def _parse_member(
    archive: zipfile.ZipFile, member: str, year: int
) -> Iterator[SectionFact]:
    source_hash = _sha256_member(archive, member)
    seen: set[int] = set()
    with archive.open(member) as binary:
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        reader = csv.reader(text)
        header = next(reader, None)
        if header != CCPC_COLUMNS:
            raise CCPCSchemaError(
                f"{member}: header does not match the 16-column allowlist: {header!r}"
            )
        for row_number, values in enumerate(reader, start=2):
            if len(values) != len(CCPC_COLUMNS):
                raise CCPCSchemaError(
                    f"{member}: row {row_number}: expected 16 columns, got {len(values)}"
                )
            source_year = _integer(values[0], "AELEC", member, row_number)
            if source_year != year:
                raise CCPCSchemaError(
                    f"{member}: row {row_number}: AELEC={source_year}, expected {year}"
                )
            state_raw = values[2].strip()
            state_num = _integer(state_raw, "EDOCVE", member, row_number)
            if not 1 <= state_num <= 32:
                raise CCPCSchemaError(f"{member}: row {row_number}: invalid EDOCVE={state_raw!r}")
            dataset_id = uuid5(
                NAMESPACE_URL,
                f"ccpc:national:{normalize_code(state_raw, 2)}:{year}:{source_hash}",
            )
            municipality_raw = values[4].strip()
            municipality_num = _integer(municipality_raw, "MPIOCVE", member, row_number)
            if not 1 <= municipality_num <= 999:
                raise CCPCSchemaError(
                    f"{member}: row {row_number}: invalid MPIOCVE={municipality_raw!r}"
                )
            section = values[6].strip()
            section_num = _integer(section, "SECCION", member, row_number)
            if not 0 <= section_num < 100_000:
                raise CCPCSchemaError(f"{member}: row {row_number}: invalid SECCION={section!r}")
            def_raw = values[8]
            def_num = _integer(def_raw, "DEF", member, row_number, nullable=True)
            if def_num is not None and not 1 <= def_num <= 99:
                raise CCPCSchemaError(f"{member}: row {row_number}: invalid DEF={def_raw!r}")
            sex = _integer(values[10], "SEXO", member, row_number)
            if sex not in ({0, 1, 2} if year == 2024 else {0, 1}):
                raise CCPCSchemaError(f"{member}: row {row_number}: invalid SEXO={sex}")
            age = _integer(values[11], "EDAD", member, row_number)
            if not 0 <= age <= 255:
                raise CCPCSchemaError(f"{member}: row {row_number}: invalid EDAD={age}")
            if values[7].strip() not in {"U", "M", "R"}:
                raise CCPCSchemaError(
                    f"{member}: row {row_number}: invalid TIPOSEC={values[7]!r}"
                )
            counts = [
                _integer(values[_FIELDS[field]], field, member, row_number)
                for field in ("LN", "SV", "NV", "NS")
            ]
            ln, sv, nv, ns = counts
            if min(counts) < 0:
                raise CCPCSchemaError(f"{member}: row {row_number}: negative counts {counts}")
            if ln != sv + nv + ns:
                raise CCPCSchemaError(
                    f"{member}: row {row_number}: LN={ln} != SV+NV+NS={sv + nv + ns}"
                )
            key = _row_key(values, member, row_number)
            if key in seen:
                raise CCPCSchemaError(
                    f"{member}: row {row_number}: duplicate key "
                    f"(EDOCVE={normalize_code(state_raw, 2)}, "
                    f"MPIOCVE={normalize_code(municipality_raw, 3)}, "
                    f"SECCION={section}, SEXO={sex}, EDAD={age})"
                )
            seen.add(key)
            district_code = normalize_code(str(def_num), 2) if def_num is not None else None
            yield SectionFact(
                year=year,
                state_code=normalize_code(state_raw, 2),
                municipality_code=normalize_code(municipality_raw, 3),
                section=section,
                district_2021=district_code if year <= 2021 else None,
                district_2023=district_code if year == 2024 else None,
                sex=values[10].strip(),
                age=age,
                section_type=values[7].strip(),
                state_name=values[3].strip(),
                municipality_name=values[5].strip(),
                ln=ln,
                sv=sv,
                nv=nv,
                ns=ns,
                source_hash=source_hash,
                source_row=row_number,
                dataset_version_id=dataset_id,
                source_state_code=state_raw,
                source_municipality_code=municipality_raw,
                source_district=def_raw,
            )


def read_national_ccpc(archive: Path, year: int) -> Iterator[SectionFact]:
    """Yield validated facts from each CSV member in a national year ZIP."""
    if year not in NATIONAL_YEARS:
        raise ValueError(f"unsupported CCPC year: {year}")
    with zipfile.ZipFile(archive) as zipped:
        members = sorted(
            name for name in zipped.namelist() if name.lower().endswith(".csv")
        )
        if len(members) != 32:
            raise CCPCSchemaError(f"{archive.name}: expected 32 CSV members, got {len(members)}")
        for member in members:
            yield from _parse_member(zipped, member, year)


def aggregate_national_municipal(
    facts: Iterable[SectionFact],
) -> list[NationalMunicipalObservation]:
    """Aggregate counts and LN-based demographics by state/municipality/year."""
    groups: dict[tuple[int, str, str], dict] = {}
    for fact in facts:
        key = (fact.year, fact.state_code, fact.municipality_code)
        group = groups.setdefault(
            key,
            {
                "state_name": fact.state_name,
                "municipality_name": fact.municipality_name,
                "ln": 0,
                "sv": 0,
                "nv": 0,
                "ns": 0,
                "young": 0,
                "senior": 0,
                "rural": 0,
                "versions": set(),
            },
        )
        for field in ("ln", "sv", "nv", "ns"):
            group[field] += getattr(fact, field)
        if 18 <= fact.age <= 29:
            group["young"] += fact.ln
        if fact.age >= 60:
            group["senior"] += fact.ln
        if fact.section_type == "R":
            group["rural"] += fact.ln
        if fact.dataset_version_id:
            group["versions"].add(str(fact.dataset_version_id))

    observations = []
    for (year, state_code, municipality_code), group in sorted(groups.items()):
        ln = group["ln"]
        reasons = []
        if group["sv"] + group["nv"] < 1000:
            reasons.append("insufficient_known_votes")
        if ln == 0 or group["ns"] / ln > 0.10:
            reasons.append("unknown_share_above_0.10")
        observations.append(
            NationalMunicipalObservation(
                year=year,
                state_code=state_code,
                municipality_code=municipality_code,
                state_name=group["state_name"],
                municipality_name=group["municipality_name"],
                ln=ln,
                sv=group["sv"],
                nv=group["nv"],
                ns=group["ns"],
                young_share=group["young"] / ln if ln else None,
                senior_share=group["senior"] / ln if ln else None,
                rural_share=group["rural"] / ln if ln else None,
                eligible=not reasons,
                quality_reasons=tuple(reasons),
                source_version_ids=tuple(sorted(group["versions"])),
            )
        )
    return observations


@dataclass(frozen=True)
class NationalIngestReport:
    row_count: int
    csv_count: int
    municipality_observation_count: int
    municipality_count: int
    district_count: int
    mismatch_count: int
    blank_def_count: int
    aggregate_sha256: str


def _atomic_json(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def ingest_national(source_dir: Path, output_dir: Path) -> NationalIngestReport:
    """Ingest six verified national ZIPs to atomic year-partitioned Parquet files."""
    from pyarrow import Table, parquet

    source_dir, output_dir = Path(source_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_municipal: list[dict] = []
    source_records: list[dict] = []
    total_rows = blank_defs = mismatches = 0
    districts_2023: set[tuple[str, str]] = set()
    aggregate_digest = hashlib.sha256()

    for year in NATIONAL_YEARS:
        archive_path = source_dir / f"ccpc-{year}.zip"
        if not archive_path.is_file():
            raise FileNotFoundError(f"missing national CCPC archive: {archive_path}")
        zip_digest = hashlib.sha256()
        with archive_path.open("rb") as zip_handle:
            for chunk in iter(lambda: zip_handle.read(1024 * 1024), b""):
                zip_digest.update(chunk)
        zip_hash = zip_digest.hexdigest()
        with zipfile.ZipFile(archive_path) as archive:
            csv_members = sorted(n for n in archive.namelist() if n.lower().endswith(".csv"))
            if len(csv_members) != 32:
                raise CCPCSchemaError(f"{archive_path.name}: expected 32 CSV members")
            member_info = []
            year_municipal: dict[tuple[str, str], dict] = {}
            tmp_path = output_dir / f".ccpc-section-{year}.parquet.tmp"
            writer = None
            try:
                for member in csv_members:
                    csv_hash = _sha256_member(archive, member)
                    count = 0
                    state_code = None
                    version_id = None
                    # Parse one member at a time; batches bound section-fact RAM.
                    batch: list[dict] = []
                    for fact in _parse_member(archive, member, year):
                        if state_code is None:
                            state_code = fact.state_code
                            version_id = str(fact.dataset_version_id)
                        count += 1
                        total_rows += 1
                        if fact.source_district is None or not fact.source_district.strip():
                            blank_defs += 1
                        if fact.ln != fact.sv + fact.nv + fact.ns:
                            mismatches += 1
                        if fact.district_2023:
                            districts_2023.add((fact.state_code, fact.district_2023))
                        key = (fact.state_code, fact.municipality_code)
                        group = year_municipal.setdefault(
                            key,
                            {
                                "state_name": fact.state_name,
                                "municipality_name": fact.municipality_name,
                                "ln": 0,
                                "sv": 0,
                                "nv": 0,
                                "ns": 0,
                                "young": 0,
                                "senior": 0,
                                "rural": 0,
                                "versions": set(),
                            },
                        )
                        for field in ("ln", "sv", "nv", "ns"):
                            group[field] += getattr(fact, field)
                        if 18 <= fact.age <= 29:
                            group["young"] += fact.ln
                        if fact.age >= 60:
                            group["senior"] += fact.ln
                        if fact.section_type == "R":
                            group["rural"] += fact.ln
                        group["versions"].add(str(fact.dataset_version_id))
                        batch.append(
                            fact.__dict__
                            | {"dataset_version_id": str(fact.dataset_version_id)}
                        )
                        if len(batch) >= 20_000:
                            table = Table.from_pylist(batch)
                            if writer is None:
                                writer = parquet.ParquetWriter(
                                    tmp_path, table.schema, compression="zstd"
                                )
                            writer.write_table(table)
                            batch.clear()
                    if batch:
                        table = Table.from_pylist(batch)
                        if writer is None:
                            writer = parquet.ParquetWriter(
                                tmp_path, table.schema, compression="zstd"
                            )
                        writer.write_table(table)
                    member_info.append(
                        {
                            "state_code": state_code,
                            "member": member,
                            "sha256": csv_hash,
                            "dataset_version_id": version_id,
                            "rows": count,
                        }
                    )
                if writer is not None:
                    writer.close()
                os.replace(tmp_path, output_dir / f"ccpc-section-{year}.parquet")
            except BaseException:
                if writer is not None:
                    writer.close()
                tmp_path.unlink(missing_ok=True)
                raise
        for (state_code, municipality_code), group in sorted(year_municipal.items()):
            ln = group["ln"]
            reasons = []
            if group["sv"] + group["nv"] < 1000:
                reasons.append("insufficient_known_votes")
            if ln == 0 or group["ns"] / ln > 0.10:
                reasons.append("unknown_share_above_0.10")
            record = {
                "year": year,
                "state_code": state_code,
                "municipality_code": municipality_code,
                "state_name": group["state_name"],
                "municipality_name": group["municipality_name"],
                "ln": ln,
                "sv": group["sv"],
                "nv": group["nv"],
                "ns": group["ns"],
                "young_share": group["young"] / ln if ln else None,
                "senior_share": group["senior"] / ln if ln else None,
                "rural_share": group["rural"] / ln if ln else None,
                "eligible": not reasons,
                "quality_reasons": reasons,
                "source_version_ids": sorted(group["versions"]),
            }
            all_municipal.append(record)
            aggregate_digest.update(
                json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
            )
            aggregate_digest.update(b"\n")
        source_records.append(
            {
                "year": year,
                "source_url": NATIONAL_ZIP_URLS[year],
                "zip": archive_path.name,
                "zip_sha256": zip_hash,
                "last_modified": "2025-08-13" if year == 2024 else "2022-04-18",
                "csv_members": member_info,
                "source_row_count": sum(row["rows"] for row in member_info),
                "dataset_version_count": len(member_info),
            }
        )

    # CSV is intentionally used for aggregates to avoid holding a second full
    # pandas frame; the artifact is small (at most 14,858 observations).
    aggregate_path = output_dir / "municipal-observations.csv"
    temp_aggregate = output_dir / ".municipal-observations.csv.tmp"
    with temp_aggregate.open("w", encoding="utf-8", newline="") as handle:
        columns = list(all_municipal[0]) if all_municipal else []
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_municipal)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_aggregate, aggregate_path)
    report = NationalIngestReport(
        row_count=total_rows,
        csv_count=sum(len(source["csv_members"]) for source in source_records),
        municipality_observation_count=len(all_municipal),
        municipality_count=sum(1 for record in all_municipal if record["year"] == 2024),
        district_count=len(districts_2023),
        mismatch_count=mismatches,
        blank_def_count=blank_defs,
        aggregate_sha256=aggregate_digest.hexdigest(),
    )
    _atomic_json(
        output_dir / "national-ingest.json",
        {
            "row_count": report.row_count,
            "csv_count": report.csv_count,
            "municipality_observation_count": report.municipality_observation_count,
            "municipality_count": report.municipality_count,
            "district_count": report.district_count,
            "mismatch_count": report.mismatch_count,
            "blank_def_count": report.blank_def_count,
            "aggregate_sha256": report.aggregate_sha256,
            "sources": source_records,
        },
    )
    return report


__all__ = [
    "NATIONAL_YEARS",
    "NationalIngestReport",
    "aggregate_national_municipal",
    "ingest_national",
    "read_national_ccpc",
]
