"""Domain types for CCPC ingestion.

Defines the raw :class:`CCPCRow`, the municipal aggregation key
:class:`MunicipalityKey`, the aggregated :class:`MunicipalObservation`, the source
manifest :class:`SourceManifest`, the territorial identity enums and the
deterministic ``uuid5`` helpers used to identify datasets, origin observations and
reference territories reproducibly (no random UUIDs).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

JALISCO_STATE_CODE = "14"
JALISCO_STATE_NAME = "JALISCO"
REFERENCE_DATE = "2025-12-15"

#: The six CCPC election years ingested for Jalisco (fixed, ascending).
ELECTION_YEARS: tuple[int, ...] = (2009, 2012, 2015, 2018, 2021, 2024)

#: Exact 16-column allowlist, in the source's column order.
CCPC_COLUMNS = [
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

#: ``TIPOSEC`` section types (Urbana, Mixta, Rural).
SECTION_TYPES = frozenset({"U", "M", "R"})

#: ``SEXO`` values valid in every year; 2024 additionally allows ``2``.
SEX_VALUES_HISTORICAL = frozenset({0, 1})
SEX_VALUES_2024 = frozenset({0, 1, 2})


class CCPCSchemaError(ValueError):
    """Raised when a CCPC CSV violates the 16-column allowlist or a constraint."""


class IdentityStatus(StrEnum):
    """Catalogue identity between source and reference territories."""

    verified_catalogue = "verified_catalogue"
    ambiguous = "ambiguous"
    known_changed = "known_changed"


class FootprintStatus(StrEnum):
    """Historical footprint comparability (never inferred as equality)."""

    verified_equal = "verified_equal"
    not_verified = "not_verified"
    known_changed = "known_changed"


def normalize_code(value: str, width: int) -> str:
    """Zero-pad an INE code to ``width`` digits, preserving the original value."""
    return value.strip().zfill(width)


def territory_id(state_code: str, municipality_code: str) -> UUID:
    """Reference identity (INE 2025 cut) for a municipality."""
    return uuid5(
        NAMESPACE_URL,
        f"ine:{state_code}:municipality:{municipality_code}:{REFERENCE_DATE}",
    )


def observation_id(
    state_code: str,
    municipality_code: str,
    year: int,
    source_version_id: UUID,
) -> UUID:
    """Origin identity for one dataset-version-scoped municipality/year row.

    Loading a second dataset version for the same municipality/year must create a
    distinct observation (and origin territory), not silently overwrite the first
    version's provenance. The ``source_version_id`` is therefore part of the
    deterministic ``uuid5`` identity.
    """
    return uuid5(
        NAMESPACE_URL,
        f"ccpc:{state_code}:municipality:{municipality_code}:{year}"
        f":dataset:{source_version_id}",
    )


def dataset_version_id(year: int, sha256: str) -> UUID:
    """Dataset version identity, derived from the CSV content hash."""
    return uuid5(NAMESPACE_URL, f"ccpc:{JALISCO_STATE_CODE}:dataset:{year}:{sha256}")


@dataclass(frozen=True)
class MunicipalityKey:
    """A municipality identity: 2-digit state code + 3-digit INE code."""

    state_code: str
    municipality_code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_code", normalize_code(self.state_code, 2))
        object.__setattr__(
            self, "municipality_code", normalize_code(self.municipality_code, 3)
        )


@dataclass(frozen=True)
class CCPCRow:
    """One validated source row (section × sex × age cell).

    ``municipality_code`` and ``state_code`` are normalized to their fixed widths
    (3 and 2 digits) on construction, preserving the original INE code value.
    """

    year: int
    election_date: str
    state_code: str
    state_name: str
    municipality_code: str
    municipality_name: str
    section: str
    section_type: str
    federal_district: int | None
    local_district: int | None
    sex: int
    age: int
    ln: int
    sv: int
    nv: int
    ns: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_code", normalize_code(self.state_code, 2))
        object.__setattr__(
            self, "municipality_code", normalize_code(self.municipality_code, 3)
        )


@dataclass
class MunicipalObservation:
    """Aggregated municipal counts and demographic shares for one year.

    ``source_version_id`` is assigned by the pipeline once the CSV content hash is
    known; ``aggregate_municipal`` leaves it ``None``. Rates and quality are
    derived via :func:`participa_geo.indicators.calculations.calculate_indicators`
    and ``assess_quality``, not stored here.
    """

    key: MunicipalityKey
    year: int
    ln: int
    sv: int
    nv: int
    ns: int
    municipality_name: str
    young_share: float | None = None
    senior_share: float | None = None
    rural_share: float | None = None
    source_version_id: UUID | None = None


@dataclass(frozen=True)
class SourceManifest:
    """A verified official CCPC source: national URL, member, checksum, date."""

    year: int
    source_url: str
    member: str
    sha256: str
    encoding: str = "utf-8-sig"
    available_at: datetime | None = None

    @property
    def file_name(self) -> str:
        return f"jalisco-{self.year}.csv"

    @property
    def version_id(self) -> UUID:
        return dataset_version_id(self.year, self.sha256)

    def as_dataset_version(self) -> DatasetVersion:
        """Project this manifest onto the persisted :class:`DatasetVersion`."""
        return DatasetVersion(
            year=self.year,
            source_url=self.source_url,
            member=self.member,
            sha256=self.sha256,
            encoding=self.encoding,
            available_at=self.available_at,
        )


@dataclass(frozen=True)
class DatasetVersion:
    """The ``dataset_version`` record for one CCPC source (Spec §10).

    ``id`` is deterministic: ``uuid5(NAMESPACE_URL, 'ccpc:14:dataset:{year}:{sha256}')``,
    so re-loading the same source never creates a duplicate. Publication date,
    licence/conditions and dictionary are nullable: they are recorded only when
    known (redistribution terms are reviewed in T9, never invented here).
    """

    year: int
    source_url: str
    member: str
    sha256: str
    encoding: str = "utf-8-sig"
    publication_date: date | None = None
    available_at: datetime | None = None
    license_conditions: str | None = None
    dictionary: dict | None = None

    @property
    def id(self) -> UUID:
        return dataset_version_id(self.year, self.sha256)


__all__ = [
    "CCPC_COLUMNS",
    "CCPCRow",
    "CCPCSchemaError",
    "DatasetVersion",
    "ELECTION_YEARS",
    "FootprintStatus",
    "IdentityStatus",
    "JALISCO_STATE_CODE",
    "JALISCO_STATE_NAME",
    "MunicipalObservation",
    "MunicipalityKey",
    "REFERENCE_DATE",
    "SECTION_TYPES",
    "SEX_VALUES_2024",
    "SEX_VALUES_HISTORICAL",
    "SourceManifest",
    "dataset_version_id",
    "normalize_code",
    "observation_id",
    "territory_id",
]
