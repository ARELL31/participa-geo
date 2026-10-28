"""Validated section lineage and plan-2023 district reconstruction.

The Access database is an offline source only. Runtime ingestion reads the
versioned CSV exported from its official history table; no Access driver is
required in the application.
"""

from __future__ import annotations

import csv
import re
import struct
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SOURCE_YEARS = (2009, 2012, 2015, 2018, 2021, 2024)
TARGET_DISTRICT_COLUMN = "Nueva_Dttacion_2023"
HISTORY_TABLE = "HISTORICO_SECC_ELECT_PEF1994-PEF2024_CORTE_diciembre2025"
MOVEMENT_COLUMNS = ("PRIMER_MOVIMIENTO", "SEGUNDO_MOVIMIENTO", "TERCER_MOVIMIENTO")
_SINGULAR_FUSION = re.compile(
    r"\bSE\s+FUSIONA\s+A\s+(?:LA\s+)?(?:SECCION|SECC\.?)?\s*0*(\d{1,5})\b",
    re.IGNORECASE,
)


class ContinuityError(ValueError):
    """An official lineage input is inconsistent or unsafe to use."""


@dataclass(frozen=True)
class SectionFactCount:
    year: int
    state_code: str
    municipality_code: str
    section: str
    district_2021: str | None
    district_2023: str | None
    ln: int
    sv: int
    nv: int
    ns: int


@dataclass(frozen=True)
class SectionContinuity:
    source_year: int
    state_code: str
    source_section: str
    target_section: str | None
    target_district: str | None
    status: Literal["matched", "unmatched"]
    evidence: str


@dataclass(frozen=True)
class ContinuityReport:
    source_year: int
    links: tuple[SectionContinuity, ...]
    matched_count: int
    unmatched_count: int
    duplicate_count: int = 0


@dataclass(frozen=True)
class ReferenceAudit:
    column: str
    common_section_count: int
    ccpc_mismatches: int
    mgs_mismatches: int
    ccpc_only_count: int
    mgs_only_count: int


@dataclass(frozen=True)
class Coverage:
    year: int
    state_code: str
    district_code: str
    matched_ln: int
    reference_ln: int
    coverage: float
    status: Literal["eligible", "insufficient"]
    district_gate_passed: bool
    national_gate_passed: bool
    national_threshold: float = 0.98
    district_threshold: float = 0.95


@dataclass(frozen=True)
class DistrictObservation:
    year: int
    state_code: str
    district_code: str
    district_plan: str
    section_count: int
    ln: int
    sv: int
    nv: int
    ns: int


@dataclass(frozen=True)
class MunicipalityDistrictPair:
    state_code: str
    municipality_code: str
    district_code: str
    section_count: int
    is_split: bool


@dataclass(frozen=True)
class MunicipalityDistrictObservation:
    year: int
    state_code: str
    municipality_code: str
    district_code: str
    district_plan: str
    section_count: int
    ln: int
    sv: int
    nv: int
    ns: int


def _code(value: object, width: int) -> str:
    raw = str(value).strip()
    if not raw:
        raise ContinuityError("empty geographic code")
    try:
        return str(int(raw)).zfill(width)
    except ValueError:
        return raw.zfill(width)


def _section(value: object) -> str:
    raw = str(value).strip()
    try:
        return str(int(raw))
    except ValueError:
        return raw


def read_historical_catalogue(path: Path) -> list[dict[str, str]]:
    """Read the official mdb-export CSV and reject malformed/duplicate keys."""
    if not path.is_file():
        raise ContinuityError(f"official historical CSV not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "cve_ent",
            "seccion",
            TARGET_DISTRICT_COLUMN,
            *(f"Distrito_PEF{year}" for year in SOURCE_YEARS if year != 2024),
            *MOVEMENT_COLUMNS,
            "seccion_baja",
            "seccion_movim_parcial",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            absent = sorted(required.difference(reader.fieldnames or []))
            raise ContinuityError(f"historical CSV missing required columns: {absent}")
        rows = list(reader)
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (_code(row["cve_ent"], 2), _section(row["seccion"]))
        if key in seen:
            raise ContinuityError(f"duplicate official history key: {key}")
        seen.add(key)
    return rows


def _read_dbf_records(raw: bytes) -> Iterable[dict[str, str]]:
    """Read the simple character/numeric fields needed from an MGS DBF file."""
    if len(raw) < 33 or raw[0] not in (0x03, 0x30, 0x31, 0x32, 0x83, 0x8B):
        raise ContinuityError("invalid or unsupported MGS DBF header")
    record_count = struct.unpack_from("<I", raw, 4)[0]
    header_length, record_length = struct.unpack_from("<HH", raw, 8)
    fields: list[tuple[str, int]] = []
    offset = 32
    while offset < header_length and raw[offset] != 0x0D:
        descriptor = raw[offset : offset + 32]
        if len(descriptor) != 32:
            raise ContinuityError("truncated DBF field descriptor")
        name = descriptor[:11].split(b"\0", 1)[0].decode("ascii").strip().lower()
        length = descriptor[16]
        if not name or length == 0:
            raise ContinuityError("invalid MGS DBF field")
        fields.append((name, length))
        offset += 32
    if header_length + record_count * record_length > len(raw):
        raise ContinuityError("truncated MGS DBF records")
    for index in range(record_count):
        record = raw[
            header_length + index * record_length : header_length + (index + 1) * record_length
        ]
        if record[:1] == b"*":
            continue
        cursor = 1
        values = {}
        for name, width in fields:
            values[name] = record[cursor : cursor + width].decode("cp1252").strip()
            cursor += width
        yield values


def read_mgs_sections(archive_dir: Path) -> list[dict[str, str]]:
    """Read section identities and MGS 2025 plan assignments from the 32 ZIPs."""
    result: list[dict[str, str]] = []
    archives = sorted(archive_dir.glob("[0-9][0-9].zip"))
    if len(archives) != 32:
        raise ContinuityError(f"expected 32 MGS entity ZIPs, found {len(archives)}")
    keys: set[tuple[str, str]] = set()
    for archive in archives:
        with zipfile.ZipFile(archive) as zipped:
            names = [name for name in zipped.namelist() if name.lower().endswith("/seccion.dbf")]
            if len(names) != 1:
                raise ContinuityError(
                    f"{archive.name}: expected one SECCION.dbf, found {len(names)}"
                )
            for row in _read_dbf_records(zipped.read(names[0])):
                missing = {"entidad", "municipio", "seccion", "distrito_f"}.difference(row)
                if missing:
                    raise ContinuityError(
                        f"{archive.name}: MGS DBF missing columns {sorted(missing)}"
                    )
                record = {
                    "state_code": _code(row["entidad"], 2),
                    "municipality_code": _code(row["municipio"], 3),
                    "section": _section(row["seccion"]),
                    "district_2023": _code(row["distrito_f"], 2),
                }
                key = (record["state_code"], record["section"])
                if key in keys:
                    raise ContinuityError(f"duplicate MGS section key: {key}")
                keys.add(key)
                result.append(record)
    return result


def read_district_labels(path: Path) -> dict[tuple[str, str], str]:
    """Read official district headquarters; fall back to a neutral entity label."""
    labels: dict[tuple[str, str], str] = {}
    if not path.is_file():
        return labels
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        required = {"ENTIDAD", "NOMBRE ENTIDAD", "DISTRITO", "NOMBRE LOCALIDAD"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ContinuityError("official district-headquarters catalogue has invalid schema")
        for row in reader:
            key = (_code(row["ENTIDAD"], 2), _code(row["DISTRITO"], 2))
            locality = row["NOMBRE LOCALIDAD"].strip()
            state = row["NOMBRE ENTIDAD"].strip()
            label = (
                f"Distrito {key[1]} — {locality}, {state}"
                if locality
                else f"Distrito {key[1]} — {state}"
            )
            if key in labels:
                raise ContinuityError(f"duplicate official district headquarters key: {key}")
            labels[key] = label
    return labels


def _row_index(
    rows: Iterable[Mapping[str, object]], label: str
) -> dict[tuple[str, str], Mapping[str, object]]:
    indexed = {}
    for row in rows:
        key = (
            _code(row["state_code"] if "state_code" in row else row["cve_ent"], 2),
            _section(row["section"] if "section" in row else row["seccion"]),
        )
        if key in indexed:
            raise ContinuityError(f"duplicate {label} section key: {key}")
        indexed[key] = row
    return indexed


def validate_2023_reference(
    historical_rows: Iterable[Mapping[str, object]],
    mgs_sections: Iterable[Mapping[str, object]],
    ccpc_2024_sections: Iterable[SectionFactCount],
) -> ReferenceAudit:
    """Cross-check the selected official field against both 2024 sources."""
    hist = _row_index(historical_rows, "historical")
    mgs = _row_index(mgs_sections, "MGS")
    ccpc = {
        (fact.state_code, _section(fact.section)): fact
        for fact in ccpc_2024_sections
        if fact.year == 2024
    }
    common = set(hist) & set(mgs) & set(ccpc)
    ccpc_mismatches = 0
    mgs_mismatches = 0
    for key in common:
        historical_value = str(hist[key][TARGET_DISTRICT_COLUMN]).strip()
        mgs_value = _code(mgs[key]["district_2023"], 2)
        ccpc_value = ccpc[key].district_2023
        if not historical_value or ccpc_value is None:
            raise ContinuityError(f"missing 2023 reference assignment for common section {key}")
        selected = _code(historical_value, 2)
        ccpc_mismatches += selected != _code(ccpc_value, 2)
        mgs_mismatches += selected != mgs_value
    return ReferenceAudit(
        column=TARGET_DISTRICT_COLUMN,
        common_section_count=len(common),
        ccpc_mismatches=ccpc_mismatches,
        mgs_mismatches=mgs_mismatches,
        ccpc_only_count=len(set(ccpc) - set(mgs)),
        mgs_only_count=len(set(mgs) - set(ccpc)),
    )


def _movement_text(row: Mapping[str, object]) -> str:
    return " ".join(str(row.get(column, "") or "").strip() for column in MOVEMENT_COLUMNS)


def _explicit_fusion_target(row: Mapping[str, object]) -> tuple[str | None, str | None]:
    """Return only a singular, explicit whole-section fusion destination."""
    text = _movement_text(row)
    if not text or str(row.get("seccion_movim_parcial", "")).strip():
        return None, None
    matches = {_section(match.group(1)) for match in _SINGULAR_FUSION.finditer(text)}
    if len(matches) != 1:
        return None, None
    return next(iter(matches)), text.strip()


def build_continuity(
    historical_rows: Iterable[Mapping[str, object]],
    mgs_sections: Iterable[Mapping[str, object]],
    facts: Iterable[SectionFactCount],
    *,
    source_year: int,
) -> ContinuityReport:
    """Link each source-year section only through confirmed official lineage.

    Stable section identifiers require a non-null source-year district in the
    official catalog, a non-null 2023 district, a matching MGS plan assignment,
    and no retirement/partial-movement flag. Whole-section fusions are accepted
    only when the official movement note names one existing target section.
    """
    if source_year not in SOURCE_YEARS:
        raise ContinuityError(f"unsupported CCPC year: {source_year}")
    hist = _row_index(historical_rows, "historical")
    mgs = _row_index(mgs_sections, "MGS")
    facts_by_key: dict[tuple[str, str], SectionFactCount] = {}
    for fact in facts:
        if fact.year != source_year:
            continue
        key = (fact.state_code, _section(fact.section))
        if key in facts_by_key:
            raise ContinuityError(f"duplicate section aggregate for {source_year}: {key}")
        facts_by_key[key] = fact

    source_column = f"Distrito_PEF{source_year}"
    links = []
    for key, fact in sorted(facts_by_key.items()):
        history_row = hist.get(key)
        if source_year != 2024 and fact.district_2021 is None:
            links.append(
                SectionContinuity(
                    source_year,
                    key[0],
                    key[1],
                    None,
                    None,
                    "unmatched",
                    "CCPC DEF is blank; not imputed",
                )
            )
            continue
        if history_row is None:
            links.append(
                SectionContinuity(
                    source_year,
                    key[0],
                    key[1],
                    None,
                    None,
                    "unmatched",
                    "no official historical-catalog row",
                )
            )
            continue
        if source_year == 2024:
            target = mgs.get(key)
            source_district = fact.district_2023
            official_district = history_row.get(TARGET_DISTRICT_COLUMN)
            if source_district and official_district:
                target_district = _code(source_district, 2)
                mgs_agrees = target is None or _code(target["district_2023"], 2) == target_district
                if mgs_agrees and target_district == _code(official_district, 2):
                    evidence = f"{TARGET_DISTRICT_COLUMN}; CCPC 2024 DEF"
                    evidence += "; MGS 2025 SECCION.distrito_f" if target else "; no MGS geometry"
                    links.append(
                        SectionContinuity(
                            2024, key[0], key[1], key[1], target_district, "matched", evidence
                        )
                    )
                    continue
            links.append(
                SectionContinuity(
                    2024,
                    key[0],
                    key[1],
                    None,
                    None,
                    "unmatched",
                    "no exact 2024 CCPC/MGS/catalogue agreement",
                )
            )
            continue

        if not str(history_row.get(source_column, "") or "").strip():
            links.append(
                SectionContinuity(
                    source_year,
                    key[0],
                    key[1],
                    None,
                    None,
                    "unmatched",
                    f"{source_column} is blank in official catalog",
                )
            )
            continue

        target_district_value = str(history_row.get(TARGET_DISTRICT_COLUMN, "") or "").strip()
        target = mgs.get(key)
        has_ambiguous_movement = bool(
            str(history_row.get("seccion_baja", "") or "").strip()
            or str(history_row.get("seccion_movim_parcial", "") or "").strip()
        )
        if target and target_district_value and not has_ambiguous_movement:
            target_district = _code(target["district_2023"], 2)
            if _code(target_district_value, 2) == target_district:
                links.append(
                    SectionContinuity(
                        source_year,
                        key[0],
                        key[1],
                        key[1],
                        target_district,
                        "matched",
                        f"official stable section row; {source_column} and "
                        f"{TARGET_DISTRICT_COLUMN}; MGS 2025 SECCION",
                    )
                )
                continue

        target_section, movement = _explicit_fusion_target(history_row)
        target_key = (key[0], target_section) if target_section else None
        target_record = mgs.get(target_key) if target_key else None
        target_hist = hist.get(target_key) if target_key else None
        if (
            target_record
            and target_hist
            and str(target_hist.get(TARGET_DISTRICT_COLUMN, "") or "").strip()
        ):
            target_district = _code(target_record["district_2023"], 2)
            if _code(target_hist[TARGET_DISTRICT_COLUMN], 2) == target_district:
                links.append(
                    SectionContinuity(
                        source_year,
                        key[0],
                        key[1],
                        target_section,
                        target_district,
                        "matched",
                        f"official full-section movement: {movement}",
                    )
                )
                continue

        reason = (
            "partial/retired section has no validated singular current target"
            if has_ambiguous_movement
            else "no validated target section in MGS/2023 catalog"
        )
        links.append(
            SectionContinuity(source_year, key[0], key[1], None, None, "unmatched", reason)
        )
    return ContinuityReport(
        source_year=source_year,
        links=tuple(links),
        matched_count=sum(link.status == "matched" for link in links),
        unmatched_count=sum(link.status == "unmatched" for link in links),
    )


def district_coverage(
    reference_2024: Iterable[SectionFactCount],
    continuity: Iterable[SectionContinuity],
    *,
    district_codes: set[tuple[str, str]],
) -> list[Coverage]:
    """Measure covered target LN against 2024 section LN, nationally and by district."""
    links = [link for link in continuity if link.status == "matched"]
    source_years = {link.source_year for link in continuity}
    if len(source_years) > 1:
        raise ContinuityError("coverage input mixes source years")
    year = next(iter(source_years), 0)
    matched_targets = {
        (link.state_code, _section(link.target_section)) for link in links if link.target_section
    }
    denominator_by_district: dict[tuple[str, str], int] = defaultdict(int)
    matched_by_district: dict[tuple[str, str], int] = defaultdict(int)
    national_reference = 0
    national_matched = 0
    for fact in reference_2024:
        if fact.year != 2024:
            continue
        if fact.ln < 0:
            raise ContinuityError("negative 2024 reference LN")
        national_reference += fact.ln
        key = (fact.state_code, _section(fact.section))
        if fact.district_2023:
            district_key = (fact.state_code, _code(fact.district_2023, 2))
            denominator_by_district[district_key] += fact.ln
            if key in matched_targets:
                matched_by_district[district_key] += fact.ln
                national_matched += fact.ln
    output: list[Coverage] = []
    for state, district in sorted(district_codes):
        key = (state, district)
        reference_ln = denominator_by_district.get(key, 0)
        matched_ln = matched_by_district.get(key, 0)
        coverage = matched_ln / reference_ln if reference_ln else 0.0
        output.append(
            Coverage(
                year,
                state,
                district,
                matched_ln,
                reference_ln,
                coverage,
                "insufficient",
                False,
                False,
            )
        )
    national_coverage = national_matched / national_reference if national_reference else 0.0
    national_passed = bool(national_reference and national_coverage >= 0.98)
    for index, item in enumerate(output):
        local_passed = bool(item.reference_ln and item.coverage >= 0.95)
        output[index] = Coverage(
            item.year,
            item.state_code,
            item.district_code,
            item.matched_ln,
            item.reference_ln,
            item.coverage,
            "eligible" if local_passed and national_passed else "insufficient",
            local_passed,
            national_passed,
        )
    output.append(
        Coverage(
            year,
            "00",
            "ALL",
            national_matched,
            national_reference,
            national_coverage,
            "eligible" if national_passed else "insufficient",
            national_passed,
            national_passed,
        )
    )
    return output


def build_municipality_district_bridge(
    mgs_sections: Iterable[Mapping[str, object]],
) -> list[MunicipalityDistrictPair]:
    """Derive the authoritative N:M municipal bridge from every MGS section."""
    section_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    districts_by_municipality: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in mgs_sections:
        state = _code(row["state_code"] if "state_code" in row else row["cve_ent"], 2)
        municipality = _code(
            row["municipality_code"] if "municipality_code" in row else row["municipio"], 3
        )
        district = _code(row["district_2023"] if "district_2023" in row else row["distrito_f"], 2)
        key = (state, municipality, district)
        section_counts[key] += 1
        districts_by_municipality[(state, municipality)].add(district)
    return [
        MunicipalityDistrictPair(
            state,
            municipality,
            district,
            count,
            len(districts_by_municipality[(state, municipality)]) > 1,
        )
        for (state, municipality, district), count in sorted(section_counts.items())
    ]


def reconstruct_district_2023(
    facts: Iterable[SectionFactCount],
    continuity: Iterable[SectionContinuity],
    mgs_sections: Iterable[Mapping[str, object]],
) -> list[DistrictObservation]:
    """Aggregate only historically linked section facts into DERFE2023 districts."""
    mgs = _row_index(mgs_sections, "MGS")
    links = {
        (link.source_year, link.state_code, _section(link.source_section)): link
        for link in continuity
    }
    groups: dict[tuple[int, str, str], dict[str, int]] = {}
    for fact in facts:
        link = links.get((fact.year, fact.state_code, _section(fact.section)))
        if not link or link.status != "matched" or link.target_section is None:
            continue
        target_key = (link.state_code, _section(link.target_section))
        target = mgs.get(target_key)
        if target is None and fact.year == 2024 and link.target_district:
            district = _code(link.target_district, 2)
        elif target is None:
            raise ContinuityError(f"continuity target absent from MGS: {target_key}")
        else:
            district = _code(target["district_2023"], 2)
        if link.target_district and _code(link.target_district, 2) != district:
            raise ContinuityError(f"continuity district disagrees with MGS for {target_key}")
        group = groups.setdefault(
            (fact.year, fact.state_code, district),
            {"sections": 0, "ln": 0, "sv": 0, "nv": 0, "ns": 0},
        )
        group["sections"] += 1
        for field in ("ln", "sv", "nv", "ns"):
            group[field] += getattr(fact, field)
    return [
        DistrictObservation(
            year,
            state,
            district,
            "DERFE2023",
            values["sections"],
            values["ln"],
            values["sv"],
            values["nv"],
            values["ns"],
        )
        for (year, state, district), values in sorted(groups.items())
    ]


def aggregate_municipality_district_year(
    facts: Iterable[SectionFactCount],
    continuity: Iterable[SectionContinuity],
    mgs_sections: Iterable[Mapping[str, object]],
) -> list[MunicipalityDistrictObservation]:
    """Aggregate section facts over the MGS municipality×district intersections."""
    mgs = _row_index(mgs_sections, "MGS")
    links = {
        (link.source_year, link.state_code, _section(link.source_section)): link
        for link in continuity
    }
    groups: dict[tuple[int, str, str, str], dict[str, int]] = {}
    for fact in facts:
        link = links.get((fact.year, fact.state_code, _section(fact.section)))
        if not link or link.status != "matched" or link.target_section is None:
            continue
        target_key = (link.state_code, _section(link.target_section))
        target = mgs.get(target_key)
        if target is None:
            # Preserve the authoritative MGS 2,581-pair universe; no CCPC-only
            # geometry-less section is added to this intersection aggregate.
            continue
        municipality = _code(target["municipality_code"], 3)
        district = _code(target["district_2023"], 2)
        group = groups.setdefault(
            (fact.year, fact.state_code, municipality, district),
            {"sections": 0, "ln": 0, "sv": 0, "nv": 0, "ns": 0},
        )
        group["sections"] += 1
        for field in ("ln", "sv", "nv", "ns"):
            group[field] += getattr(fact, field)
    return [
        MunicipalityDistrictObservation(
            year,
            state,
            municipality,
            district,
            "DERFE2023",
            values["sections"],
            values["ln"],
            values["sv"],
            values["nv"],
            values["ns"],
        )
        for (year, state, municipality, district), values in sorted(groups.items())
    ]


__all__ = [
    "Coverage",
    "ContinuityError",
    "ContinuityReport",
    "DistrictObservation",
    "MunicipalityDistrictObservation",
    "MunicipalityDistrictPair",
    "ReferenceAudit",
    "SectionContinuity",
    "SectionFactCount",
    "aggregate_municipality_district_year",
    "build_continuity",
    "build_municipality_district_bridge",
    "district_coverage",
    "read_historical_catalogue",
    "read_mgs_sections",
    "reconstruct_district_2023",
    "read_district_labels",
    "validate_2023_reference",
]
