"""Build and persist the official-history continuity audit and district bridge."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from participa_geo.ingestion.continuity import (
    SectionFactCount,
    aggregate_municipality_district_year,
    aggregate_observed_district_2024,
    build_continuity,
    build_municipality_district_bridge,
    district_coverage,
    read_district_labels,
    read_historical_catalogue,
    read_mgs_sections,
    reconstruct_district_2023,
    validate_2023_reference,
)


@dataclass(frozen=True)
class ContinuityBuildAudit:
    history_row_count: int
    mgs_section_count: int
    mgs_municipality_district_pair_count: int
    split_municipality_count: int
    plan_reference_column: str
    reference_common_count: int
    reference_ccpc_mismatches: int
    reference_mgs_mismatches: int
    ccpc_2024_without_mgs_count: int
    mgs_without_ccpc_2024_count: int
    national_coverage_by_year: dict[str, float]
    national_status_by_year: dict[str, str]
    eligible_district_count_by_year: dict[str, int]
    source_sha256: str
    csv_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_section_counts(session: Session) -> list[SectionFactCount]:
    rows = session.execute(
        text(
            "SELECT year,state_code,municipality_code,section,"
            "min(district_2021) AS district_2021,min(district_2023) AS district_2023,"
            "count(DISTINCT district_2021) AS d2021_count,"
            "count(DISTINCT district_2023) AS d2023_count,"
            "sum(ln) AS ln,sum(sv) AS sv,sum(nv) AS nv,sum(ns) AS ns "
            "FROM fact_ccpc_section GROUP BY year,state_code,municipality_code,section "
            "ORDER BY year,state_code,section"
        )
    ).mappings()
    facts = []
    for row in rows:
        if row["d2021_count"] > 1 or row["d2023_count"] > 1:
            raise ValueError(
                f"section has multiple district assignments: "
                f"{row['year']}/{row['state_code']}/{row['section']}"
            )
        facts.append(
            SectionFactCount(
                year=int(row["year"]),
                state_code=str(row["state_code"]),
                municipality_code=str(row["municipality_code"]),
                section=str(row["section"]),
                district_2021=row["district_2021"],
                district_2023=row["district_2023"],
                ln=int(row["ln"]),
                sv=int(row["sv"]),
                nv=int(row["nv"]),
                ns=int(row["ns"]),
            )
        )
    if not facts:
        raise ValueError("fact_ccpc_section is empty; ingest national CCPC first")
    return facts


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _record_dicts(records) -> list[dict]:
    return [asdict(record) for record in records]


def _coverage_copy_rows(rows: list[dict]) -> list[dict]:
    """Provide required DB columns explicitly for COPY, independent of defaults."""
    return [
        {
            **row,
            "district_code": "00" if row["district_code"] == "ALL" else row["district_code"],
            "district_plan": "DERFE2023",
        }
        for row in rows
    ]


def _copy_rows(session: Session, table: str, columns: list[str], rows: list[dict]) -> None:
    """Use PostgreSQL COPY for national-scale Task 3 artifacts."""
    if not rows:
        return
    connection = session.connection().connection.driver_connection
    statement = f"COPY {table} ({','.join(columns)}) FROM STDIN"
    with connection.cursor().copy(statement) as copy:
        for row in rows:
            copy.write_row(tuple(row[column] for column in columns))


def build_national_continuity(
    session: Session,
    *,
    historical_csv: Path,
    source_accdb: Path,
    mgs_archive_dir: Path,
    district_catalogue: Path,
    output_dir: Path,
) -> ContinuityBuildAudit:
    """Validate the official artifacts, write reports, then replace Task 3 tables."""
    history = read_historical_catalogue(historical_csv)
    mgs = read_mgs_sections(mgs_archive_dir)
    labels = read_district_labels(district_catalogue)
    facts = _load_section_counts(session)
    reference = [fact for fact in facts if fact.year == 2024]
    reference_audit = validate_2023_reference(history, mgs, reference)
    if reference_audit.ccpc_mismatches or reference_audit.mgs_mismatches:
        raise ValueError(f"2023 reference cross-check failed: {reference_audit}")

    district_codes = {(row["state_code"], row["district_2023"]) for row in mgs}
    if len(district_codes) != 300:
        raise ValueError(f"expected 300 MGS districts, found {len(district_codes)}")
    pairs = build_municipality_district_bridge(mgs)
    split_count = len({(row.state_code, row.municipality_code) for row in pairs if row.is_split})
    if len(pairs) != 2581 or split_count != 72:
        raise ValueError(
            f"MGS crosswalk drift: expected 2,581 pairs/72 split municipalities, "
            f"found {len(pairs)}/{split_count}"
        )

    continuity_reports = {
        year: build_continuity(history, mgs, facts, source_year=year)
        for year in (2009, 2012, 2015, 2018, 2021, 2024)
    }
    coverage_by_year = {
        year: district_coverage(
            reference, report.links, district_codes=district_codes, mgs_sections=mgs
        )
        for year, report in continuity_reports.items()
    }
    coverage_rows = [
        asdict(item) for year in sorted(coverage_by_year) for item in coverage_by_year[year]
    ]
    coverage_statuses = {
        (row["year"], row["state_code"], row["district_code"]): row["status"]
        for row in coverage_rows
    }
    aggregate_rows = []
    for year, report in continuity_reports.items():
        aggregate_rows.extend(
            asdict(row)
            for row in aggregate_municipality_district_year(facts, report.links, mgs)
            if row.year == year
        )
    # This validates district-level observations and the no-cross-plan rule even
    # when the year fails its publishability gate.
    district_rows = []
    for year, report in continuity_reports.items():
        observations = (
            aggregate_observed_district_2024(facts)
            if year == 2024
            else reconstruct_district_2023(facts, report.links, mgs)
        )
        district_rows.extend(
            asdict(row) for row in observations if row.year == year
        )
    observed_2024_districts = {
        (row["state_code"], row["district_code"])
        for row in district_rows
        if row["year"] == 2024
    }
    if observed_2024_districts != district_codes:
        missing = sorted(district_codes - observed_2024_districts)
        unexpected = sorted(observed_2024_districts - district_codes)
        raise ValueError(
            "2024 CCPC district totals must cover the complete MGS DERFE2023 catalogue "
            f"(missing={missing[:5]}, unexpected={unexpected[:5]})"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for year, report in continuity_reports.items():
        _write_csv(
            output_dir / f"section-continuity-{year}.csv",
            _record_dicts(report.links),
            [
                "source_year",
                "state_code",
                "source_section",
                "target_section",
                "target_district",
                "status",
                "evidence",
            ],
        )
    _write_csv(
        output_dir / "coverage-report.csv",
        coverage_rows,
        [
            "year",
            "state_code",
            "district_code",
            "matched_ln",
            "reference_ln",
            "coverage",
            "status",
            "reference_section_count",
            "matched_section_count",
            "unmatched_ccpc_section_count",
            "unmatched_ccpc_ln",
            "ccpc_without_mgs_section_count",
            "ccpc_without_mgs_ln",
            "mgs_only_section_count",
            "mgs_only_ln",
            "section_universe_gap_count",
            "district_gate_passed",
            "national_gate_passed",
            "national_threshold",
            "district_threshold",
        ],
    )
    _write_csv(
        output_dir / "bridge-section-district.csv",
        [
            {
                "state_code": row["state_code"],
                "section": row["section"],
                "district_plan": "DERFE2023",
                "municipality_code": row["municipality_code"],
                "district_code": row["district_2023"],
                "district_label": labels.get(
                    (row["state_code"], row["district_2023"]),
                    f"Distrito {row['district_2023']} — Entidad {row['state_code']}",
                ),
                "provenance": "INE MGS_UTM_SHAPEFILE_15DIC2025 SECCION",
            }
            for row in mgs
        ],
        [
            "state_code",
            "section",
            "district_plan",
            "municipality_code",
            "district_code",
            "district_label",
            "provenance",
        ],
    )
    _write_csv(
        output_dir / "bridge-municipality-district.csv",
        [dict(asdict(row), district_plan="DERFE2023") for row in pairs],
        [
            "state_code",
            "municipality_code",
            "district_code",
            "section_count",
            "is_split",
            "district_plan",
        ],
    )
    # The plan tag is repeated in this output to prevent accidental 2021/2023 use.
    for row in aggregate_rows:
        row["coverage_status"] = coverage_statuses.get(
            (row["year"], row["state_code"], row["district_code"]), "insufficient"
        )
    _write_csv(
        output_dir / "agg-municipality-district-year.csv",
        aggregate_rows,
        [
            "year",
            "state_code",
            "municipality_code",
            "district_code",
            "district_plan",
            "section_count",
            "ln",
            "sv",
            "nv",
            "ns",
            "coverage_status",
        ],
    )
    _write_csv(
        output_dir / "district-observations.csv",
        [
            dict(
                row,
                coverage_status=coverage_statuses.get(
                    (row["year"], row["state_code"], row["district_code"]), "insufficient"
                ),
            )
            for row in district_rows
        ],
        [
            "year",
            "state_code",
            "district_code",
            "district_plan",
            "section_count",
            "ln",
            "sv",
            "nv",
            "ns",
            "coverage_status",
        ],
    )
    mgs_keys = {(row["state_code"], row["section"]) for row in mgs}
    ccpc_keys = {(fact.state_code, fact.section) for fact in reference}
    _write_csv(
        output_dir / "mgs-sections-without-2024-ccpc.csv",
        [
            {
                "state_code": row["state_code"],
                "section": row["section"],
                "municipality_code": row["municipality_code"],
                "district_code": row["district_2023"],
                "status": "uncovered_no_ccpc_ln",
                "section_count": 1,
                "ln": "",
                "ln_status": "absent_no_ccpc_fact",
                "evidence": "MGS section has no 2024 CCPC fact; LN is absent, not imputed",
            }
            for row in mgs
            if (row["state_code"], row["section"]) not in ccpc_keys
        ],
        [
            "state_code",
            "section",
            "municipality_code",
            "district_code",
            "status",
            "section_count",
            "ln",
            "ln_status",
            "evidence",
        ],
    )
    _write_csv(
        output_dir / "ccpc-2024-sections-without-mgs.csv",
        [
            {
                "state_code": fact.state_code,
                "section": fact.section,
                "municipality_code": fact.municipality_code,
                "district_code": fact.district_2023,
                "ln": fact.ln,
                "status": "no_mgs_geometry",
            }
            for fact in reference
            if (fact.state_code, fact.section) not in mgs_keys
        ],
        ["state_code", "section", "municipality_code", "district_code", "ln", "status"],
    )

    source_hash = _sha256(source_accdb)
    csv_hash = _sha256(historical_csv)
    output_audit = ContinuityBuildAudit(
        history_row_count=len(history),
        mgs_section_count=len(mgs),
        mgs_municipality_district_pair_count=len(pairs),
        split_municipality_count=split_count,
        plan_reference_column=reference_audit.column,
        reference_common_count=reference_audit.common_section_count,
        reference_ccpc_mismatches=reference_audit.ccpc_mismatches,
        reference_mgs_mismatches=reference_audit.mgs_mismatches,
        ccpc_2024_without_mgs_count=reference_audit.ccpc_only_count,
        mgs_without_ccpc_2024_count=reference_audit.mgs_only_count,
        national_coverage_by_year={
            str(year): next(c.coverage for c in coverage_by_year[year] if c.district_code == "ALL")
            for year in coverage_by_year
        },
        national_status_by_year={
            str(year): next(c.status for c in coverage_by_year[year] if c.district_code == "ALL")
            for year in coverage_by_year
        },
        eligible_district_count_by_year={
            str(year): sum(
                c.status == "eligible" for c in coverage_by_year[year] if c.district_code != "ALL"
            )
            for year in coverage_by_year
        },
        source_sha256=source_hash,
        csv_sha256=csv_hash,
    )
    (output_dir / "continuity-build.json").write_text(
        json.dumps(asdict(output_audit), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Bulk replace only the Task 3 tables; raw section facts remain untouched.
    for table in (
        "agg_district_year",
        "agg_municipality_district_year",
        "district_reconstruction_coverage",
        "bridge_municipality_district",
        "bridge_section_district",
        "section_continuity",
    ):
        session.execute(text(f"DELETE FROM {table}"))
    continuity_rows = [
        dict(asdict(link), source_catalog_sha256=csv_hash)
        for report in continuity_reports.values()
        for link in report.links
    ]
    bridge_section_rows = list(
        csv.DictReader(
            (output_dir / "bridge-section-district.csv").open(encoding="utf-8", newline="")
        )
    )
    bridge_pair_rows = [dict(asdict(row), district_plan="DERFE2023") for row in pairs]
    _copy_rows(
        session,
        "section_continuity",
        [
            "source_year",
            "state_code",
            "source_section",
            "target_section",
            "target_district",
            "status",
            "evidence",
            "source_catalog_sha256",
        ],
        continuity_rows,
    )
    _copy_rows(
        session,
        "bridge_section_district",
        [
            "state_code",
            "section",
            "district_plan",
            "municipality_code",
            "district_code",
            "district_label",
            "provenance",
        ],
        bridge_section_rows,
    )
    _copy_rows(
        session,
        "bridge_municipality_district",
        [
            "state_code",
            "municipality_code",
            "district_code",
            "district_plan",
            "section_count",
            "is_split",
        ],
        bridge_pair_rows,
    )
    _copy_rows(
        session,
        "district_reconstruction_coverage",
        [
            "year",
            "state_code",
            "district_code",
            "matched_ln",
            "reference_ln",
            "coverage",
            "status",
            "reference_section_count",
            "matched_section_count",
            "unmatched_ccpc_section_count",
            "unmatched_ccpc_ln",
            "ccpc_without_mgs_section_count",
            "ccpc_without_mgs_ln",
            "mgs_only_section_count",
            "mgs_only_ln",
            "section_universe_gap_count",
            "district_plan",
        ],
        _coverage_copy_rows(coverage_rows),
    )
    _copy_rows(
        session,
        "agg_district_year",
        [
            "year",
            "state_code",
            "district_code",
            "district_plan",
            "section_count",
            "ln",
            "sv",
            "nv",
            "ns",
        ],
        [row for row in district_rows if row["year"] == 2024],
    )
    _copy_rows(
        session,
        "agg_municipality_district_year",
        [
            "year",
            "state_code",
            "municipality_code",
            "district_code",
            "district_plan",
            "section_count",
            "ln",
            "sv",
            "nv",
            "ns",
            "coverage_status",
        ],
        aggregate_rows,
    )
    session.flush()
    return output_audit


__all__ = ["ContinuityBuildAudit", "build_national_continuity"]
