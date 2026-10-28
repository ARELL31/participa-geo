"""National CCPC section-grain fact records."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SectionFact:
    year: int
    state_code: str
    municipality_code: str
    section: str
    district_2021: str | None
    district_2023: str | None
    sex: str
    age: int
    section_type: str
    state_name: str
    municipality_name: str
    ln: int
    sv: int
    nv: int
    ns: int
    source_hash: str
    source_row: int
    dataset_version_id: UUID | None = None
    source_state_code: str | None = None
    source_municipality_code: str | None = None
    source_district: str | None = None


@dataclass(frozen=True)
class NationalMunicipalObservation:
    year: int
    state_code: str
    municipality_code: str
    state_name: str
    municipality_name: str
    ln: int
    sv: int
    nv: int
    ns: int
    young_share: float | None
    senior_share: float | None
    rural_share: float | None
    eligible: bool
    quality_reasons: tuple[str, ...]
    source_version_ids: tuple[str, ...]


__all__ = ["NationalMunicipalObservation", "SectionFact"]
