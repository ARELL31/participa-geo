"""Municipal aggregation of CCPC rows.

Counts are summed before any rate is computed; demographic shares (young 18-29,
senior 60+, rural ``R``) are proportions of ``LN`` — never of ``SV``. Ages above
100 remain raw in the source row and aggregate into the 60+ (senior) bucket
without recoding the underlying data.
"""

from __future__ import annotations

from collections.abc import Iterable

from participa_geo.ingestion.schema import (
    CCPCRow,
    MunicipalityKey,
    MunicipalObservation,
)

YOUNG_AGE_MIN = 18
YOUNG_AGE_MAX = 29
SENIOR_AGE_MIN = 60


def aggregate_municipal(rows: Iterable[CCPCRow]) -> list[MunicipalObservation]:
    """Sum counts and compute LN-based shares per municipality/year.

    The result is sorted by ``(year, municipality_code)`` for determinism.
    ``source_version_id`` is left ``None``; the pipeline assigns it once the CSV
    content hash is known.
    """
    groups: dict[tuple[int, str], dict] = {}
    for row in rows:
        key = (row.year, row.municipality_code)
        group = groups.get(key)
        if group is None:
            group = {
                "state_code": row.state_code,
                "name": row.municipality_name,
                "ln": 0,
                "sv": 0,
                "nv": 0,
                "ns": 0,
                "young": 0,
                "senior": 0,
                "rural": 0,
            }
            groups[key] = group

        group["ln"] += row.ln
        group["sv"] += row.sv
        group["nv"] += row.nv
        group["ns"] += row.ns
        if YOUNG_AGE_MIN <= row.age <= YOUNG_AGE_MAX:
            group["young"] += row.ln
        if row.age >= SENIOR_AGE_MIN:
            group["senior"] += row.ln
        if row.section_type == "R":
            group["rural"] += row.ln

    observations: list[MunicipalObservation] = []
    for (year, code) in sorted(groups):
        group = groups[(year, code)]
        ln = group["ln"]
        observations.append(
            MunicipalObservation(
                key=MunicipalityKey(state_code=group["state_code"], municipality_code=code),
                year=year,
                ln=ln,
                sv=group["sv"],
                nv=group["nv"],
                ns=group["ns"],
                municipality_name=group["name"],
                young_share=(group["young"] / ln) if ln else None,
                senior_share=(group["senior"] / ln) if ln else None,
                rural_share=(group["rural"] / ln) if ln else None,
            )
        )
    return observations


__all__ = ["aggregate_municipal"]
