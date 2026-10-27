"""Reading and verification of official CCPC sources.

``read_ccpc`` is a fail-closed reader: it enforces the exact 16-column allowlist,
non-negative integer counts, the ``LN = SV + NV + NS`` accounting identity, the
year and entity, the ``U/M/R`` section type, the sex categories (0/1, plus 2 only
in 2024) and ``EDAD >= 18``. ``DEL`` and ``DEF`` are nullable (blank in 2009/2012
and ``DEL`` blank in 2024) and are retained as ``None`` — never invented. The
duplicate key ``(year, entity, municipality, section, sex, age)`` is rejected.

The verification helpers compute the SHA-256 of a CSV member and the CRC of a ZIP
member, guard ZIP paths and enforce size limits. ``fetch_source`` is the full-ZIP
fallback used by ``--fetch``; it never extracts arbitrary members.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import tempfile
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path

from participa_geo.ingestion.schema import (
    CCPC_COLUMNS,
    JALISCO_STATE_CODE,
    SECTION_TYPES,
    SEX_VALUES_2024,
    SEX_VALUES_HISTORICAL,
    CCPCRow,
    CCPCSchemaError,
    SourceManifest,
    normalize_code,
)

#: Safety limits for ``--fetch`` (full-ZIP fallback path).
MAX_ZIP_BYTES = 256 * 1024 * 1024  # 256 MiB
MAX_MEMBER_BYTES = 96 * 1024 * 1024  # 96 MiB (largest Jalisco CSV is ~38 MiB)

_FIELD_NAMES = [
    "AELEC",
    "FELECCION",
    "EDOCVE",
    "EDONOM",
    "MPIOCVE",
    "MPIONOM",
    "SECCION",
    "TIPOSEC",
    "DEF",
    "DEL",
    "SEXO",
    "EDAD",
    "LN",
    "SV",
    "NV",
    "NS",
]


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_csv_sha256(path: Path, expected_sha256: str) -> None:
    """Fail closed when a CSV's SHA-256 does not match the manifest."""
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise CCPCSchemaError(
            f"{path.name}: SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )


def _row_key(year: int, municipality: int, section: int, sex: int, age: int) -> int:
    """Pack the duplicate-detection key into a single int (no collisions)."""
    key = year - 2000
    key = (key << 10) | municipality
    key = (key << 14) | section
    key = (key << 2) | sex
    key = (key << 8) | age
    return key


def _parse_int(field: str, name: str, line_no: int, *, nullable: bool = False) -> int | None:
    stripped = field.strip()
    if nullable and stripped == "":
        return None
    try:
        return int(stripped)
    except ValueError:
        raise CCPCSchemaError(
            f"line {line_no}: field {name!r} must be an integer, got {field!r}"
        ) from None


def read_ccpc(path: Path, expected_year: int) -> Iterator[CCPCRow]:
    """Yield validated :class:`CCPCRow` instances from a Jalisco CCPC CSV."""
    seen: set[int] = set()
    allowed_sex = SEX_VALUES_2024 if expected_year == 2024 else SEX_VALUES_HISTORICAL

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != CCPC_COLUMNS:
            raise CCPCSchemaError(
                f"{path.name}: header does not match the 16-column allowlist: {header!r}"
            )

        for line_no, fields in enumerate(reader, start=2):
            if len(fields) != 16:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: expected 16 columns, got {len(fields)}"
                )

            year = _parse_int(fields[0], _FIELD_NAMES[0], line_no)
            if year != expected_year:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: AELEC={year}, expected {expected_year}"
                )

            state_code = fields[2].strip()
            if state_code != JALISCO_STATE_CODE:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: EDOCVE={state_code!r}, expected "
                    f"{JALISCO_STATE_CODE!r}"
                )

            municipality_raw = fields[4].strip()
            municipality = _parse_int(fields[4], _FIELD_NAMES[4], line_no)
            municipality_code = normalize_code(municipality_raw, 3)

            section = fields[6].strip()
            section_int = _parse_int(fields[6], _FIELD_NAMES[6], line_no)

            section_type = fields[7].strip()
            if section_type not in SECTION_TYPES:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: TIPOSEC={section_type!r} not in "
                    f"{sorted(SECTION_TYPES)!r}"
                )

            federal_district = _parse_int(fields[8], _FIELD_NAMES[8], line_no, nullable=True)
            local_district = _parse_int(fields[9], _FIELD_NAMES[9], line_no, nullable=True)

            sex = _parse_int(fields[10], _FIELD_NAMES[10], line_no)
            if sex not in allowed_sex:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: SEXO={sex} not allowed for year "
                    f"{expected_year} (allowed {sorted(allowed_sex)})"
                )

            age = _parse_int(fields[11], _FIELD_NAMES[11], line_no)
            if age < 18:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: EDAD={age} is below 18"
                )

            ln = _parse_int(fields[12], _FIELD_NAMES[12], line_no)
            sv = _parse_int(fields[13], _FIELD_NAMES[13], line_no)
            nv = _parse_int(fields[14], _FIELD_NAMES[14], line_no)
            ns = _parse_int(fields[15], _FIELD_NAMES[15], line_no)

            if ln < 0 or sv < 0 or nv < 0 or ns < 0:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: negative count "
                    f"(LN={ln}, SV={sv}, NV={nv}, NS={ns})"
                )
            if ln != sv + nv + ns:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: LN={ln} != SV+NV+NS={sv + nv + ns}"
                )

            # Defensive bounds for the packed duplicate key (far above real data).
            if not (0 <= municipality < 1024):
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: MPIOCVE={municipality} out of range"
                )
            if not (0 <= section_int < 16384):
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: SECCION={section_int} out of range"
                )
            if age >= 256:
                raise CCPCSchemaError(f"{path.name}: line {line_no}: EDAD={age} out of range")

            key = _row_key(year, municipality, section_int, sex, age)
            if key in seen:
                raise CCPCSchemaError(
                    f"{path.name}: line {line_no}: duplicate key (AELEC={year}, "
                    f"MPIOCVE={municipality_code}, SECCION={section}, SEXO={sex}, "
                    f"EDAD={age})"
                )
            seen.add(key)

            yield CCPCRow(
                year=year,
                election_date=fields[1].strip(),
                state_code=state_code,
                state_name=fields[3].strip(),
                municipality_code=municipality_code,
                municipality_name=fields[5].strip(),
                section=section,
                section_type=section_type,
                federal_district=federal_district,
                local_district=local_district,
                sex=sex,
                age=age,
                ln=ln,
                sv=sv,
                nv=nv,
                ns=ns,
            )


def extract_member_from_zip(zip_bytes: bytes, member: str, dest_dir: Path) -> Path:
    """Extract one ZIP member safely, verifying its CRC and enforcing size limits.

    Only the exact ``member`` path is extracted; ``..`` and absolute paths are
    rejected and no other member is ever written to disk.
    """
    if len(zip_bytes) > MAX_ZIP_BYTES:
        raise CCPCSchemaError(f"ZIP exceeds {MAX_ZIP_BYTES} bytes")
    normalized = member.replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        raise CCPCSchemaError(f"unsafe ZIP member path: {member!r}")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        try:
            info = archive.getinfo(member)
        except KeyError:
            raise CCPCSchemaError(f"member {member!r} not found in ZIP") from None
        if info.file_size > MAX_MEMBER_BYTES:
            raise CCPCSchemaError(f"member {member!r} exceeds {MAX_MEMBER_BYTES} bytes")

        # Reading the member verifies its CRC-32 (zipfile raises BadZipFile on CRC
        # mismatch). Members are never written before CRC verification succeeds.
        with archive.open(info) as source:
            content = source.read()

    if len(content) != info.file_size:
        raise CCPCSchemaError(
            f"member {member!r} size mismatch: expected {info.file_size}, got {len(content)}"
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / Path(member).name
    fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return target


def fetch_source(manifest: SourceManifest, dest_dir: Path) -> Path:
    """Download the full national ZIP and extract the verified Jalisco member.

    The full-ZIP path is the verified fallback; the extracted CSV's SHA-256 is
    checked against the manifest before it is returned.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / manifest.file_name
    if target.exists() and sha256_file(target) == manifest.sha256:
        return target

    with urllib.request.urlopen(manifest.source_url, timeout=60) as response:
        data = response.read(MAX_ZIP_BYTES + 1)
    if len(data) > MAX_ZIP_BYTES:
        raise CCPCSchemaError(f"{manifest.source_url}: ZIP exceeds {MAX_ZIP_BYTES} bytes")

    extracted = extract_member_from_zip(data, manifest.member, dest_dir)
    verify_csv_sha256(extracted, manifest.sha256)
    if extracted != target:
        os.replace(extracted, target)
    return target


__all__ = [
    "CCPCSchemaError",
    "extract_member_from_zip",
    "fetch_source",
    "read_ccpc",
    "sha256_file",
    "verify_csv_sha256",
]
