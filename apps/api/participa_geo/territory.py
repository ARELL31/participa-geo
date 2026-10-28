"""Canonical identity and scope rules for national territories."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

TerritoryLevel = Literal["municipality", "federal_district"]
DistrictPlan = Literal["DERFE2021", "DERFE2023"]
MUNICIPALITY_REFERENCE_DATE = "2025-12-15"


@dataclass(frozen=True)
class TerritoryKey:
    """A state-scoped municipal or plan-versioned federal district key."""

    level: TerritoryLevel
    state_code: str
    code: str
    district_plan: DistrictPlan | None = None

    def __post_init__(self) -> None:
        if self.level not in ("municipality", "federal_district"):
            raise ValueError(f"unsupported territory level: {self.level}")
        if self.district_plan not in (None, "DERFE2021", "DERFE2023"):
            raise ValueError(f"unsupported district plan: {self.district_plan}")
        object.__setattr__(self, "state_code", self.state_code.strip().zfill(2))
        width = 3 if self.level == "municipality" else 2
        object.__setattr__(self, "code", self.code.strip().zfill(width))
        if self.level == "municipality" and self.district_plan is not None:
            raise ValueError("municipality cannot have district_plan")
        if self.level == "federal_district" and self.district_plan is None:
            raise ValueError("federal_district requires district_plan")


def territory_id(key: TerritoryKey) -> UUID:
    """Return a stable UUID; municipal Jalisco IDs retain their MVP namespace."""
    if key.level == "municipality":
        identity = f"ine:{key.state_code}:municipality:{key.code}:{MUNICIPALITY_REFERENCE_DATE}"
    else:
        identity = f"ine:{key.state_code}:federal_district:{key.code}:{key.district_plan}"
    return uuid5(NAMESPACE_URL, identity)


def observation_id(key: TerritoryKey, year: int, source_version_id: UUID) -> UUID:
    """Return a stable dataset-scoped observation identity including its plan."""
    if key.level == "municipality":
        identity = (
            f"ccpc:{key.state_code}:municipality:{key.code}:{year}:dataset:{source_version_id}"
        )
    else:
        identity = (
            f"ccpc:{key.state_code}:federal_district:{key.code}:{key.district_plan}"
            f":{year}:dataset:{source_version_id}"
        )
    return uuid5(NAMESPACE_URL, identity)


def validate_scenario_territories(keys: Sequence[TerritoryKey]) -> None:
    """Reject scenario selections that mix analytical levels or district plans."""
    if not keys:
        return
    scopes = {(key.level, key.district_plan) for key in keys}
    if len(scopes) != 1:
        raise ValueError("scenario territories must use the same level and district plan")


__all__ = [
    "DistrictPlan",
    "TerritoryKey",
    "TerritoryLevel",
    "observation_id",
    "territory_id",
    "validate_scenario_territories",
]
