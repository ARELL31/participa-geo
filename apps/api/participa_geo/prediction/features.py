"""Feature construction for the interpretable temporal abstention model.

The six predictors (exact order, Spec §7) are:

1. ``same_type_abstention_pct`` — known abstention at ``t-6``, same election type.
2. ``previous_abstention_pct``   — known abstention at ``t-3`` (last ordinary).
3. ``previous_young_share``      — LN proportion 18-29 at ``t-3``.
4. ``previous_senior_share``     — LN proportion 60+ at ``t-3``.
5. ``previous_rural_share``      — LN proportion in rural sections at ``t-3``.
6. ``is_midterm``                — 1 for an intermediate election, 0 otherwise.

Every data-derived feature records its source year; ``is_midterm`` is structural
(no data origin). For the 2027 target only 2021 and 2024 are used; no 2027
demographic is ever read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from participa_geo.ingestion.schema import MunicipalObservation
from participa_geo.prediction.cohorts import Exclusion, build_cohort

#: Exact feature order (Spec §7 and the task brief).
FEATURE_ORDER: tuple[str, ...] = (
    "same_type_abstention_pct",
    "previous_abstention_pct",
    "previous_young_share",
    "previous_senior_share",
    "previous_rural_share",
    "is_midterm",
)

#: Federal election type by year (midterm = intermediate vs presidential).
MIDTERM_YEARS = frozenset({2009, 2015, 2021, 2027})
PRESIDENTIAL_YEARS = frozenset({2012, 2018, 2024})


def is_midterm_election(year: int) -> bool:
    """Return True for intermediate (midterm) federal election years."""
    if year in MIDTERM_YEARS:
        return True
    if year in PRESIDENTIAL_YEARS:
        return False
    raise ValueError(f"unknown federal election type for year {year}")


@dataclass(frozen=True)
class ExampleRow:
    """One municipality in a cohort with its features and (for training) target."""

    municipality_code: str
    municipality_name: str
    target_year: int
    target: float | None
    target_known_count: int
    features: dict[str, float]
    origins: dict[str, int | None]


@dataclass(frozen=True)
class FeatureDataset:
    """Cohort rows plus exclusions for one target year.

    ``target`` is present only for training/evaluation targets (never for 2027).
    """

    target_year: int
    rows: tuple[ExampleRow, ...]
    exclusions: tuple[Exclusion, ...]
    feature_order: tuple[str, ...] = FEATURE_ORDER


def abstention_pct(obs: MunicipalObservation) -> float | None:
    """Known abstention in percentage points (``100 * NV / (SV + NV)``)."""
    known = obs.sv + obs.nv
    return (100.0 * obs.nv / known) if known > 0 else None


def _index(
    observations: list[MunicipalObservation],
) -> dict[tuple[str, int], MunicipalObservation]:
    index: dict[tuple[str, int], MunicipalObservation] = {}
    for obs in observations:
        index[(obs.key.municipality_code, obs.year)] = obs
    return index


def build_examples(
    observations,
    target_year: int,
    identity_statuses: Mapping[str, object],
) -> FeatureDataset:
    """Build the cohort and features for ``target_year``.

    ``identity_statuses`` maps ``municipality_code`` to a
    :class:`~participa_geo.prediction.cohorts.TerritoryIdentity`. It is required:
    a municipality present in the data but absent from the mapping raises, so the
    pipeline can never silently assume an identity is verified.
    """
    observations = list(observations)
    index = _index(observations)
    names = {obs.key.municipality_code: obs.municipality_name for obs in observations}

    eligible, exclusions = build_cohort(observations, target_year, identity_statuses)

    t6 = target_year - 6
    t3 = target_year - 3
    midterm = 1.0 if is_midterm_election(target_year) else 0.0
    rows: list[ExampleRow] = []
    for code in eligible:
        same = index[(code, t6)]
        prev = index[(code, t3)]
        target_obs = index.get((code, target_year))
        features = {
            "same_type_abstention_pct": abstention_pct(same),
            "previous_abstention_pct": abstention_pct(prev),
            "previous_young_share": prev.young_share,
            "previous_senior_share": prev.senior_share,
            "previous_rural_share": prev.rural_share,
            "is_midterm": midterm,
        }
        origins = {
            "same_type_abstention_pct": t6,
            "previous_abstention_pct": t3,
            "previous_young_share": t3,
            "previous_senior_share": t3,
            "previous_rural_share": t3,
            "is_midterm": None,
        }
        rows.append(
            ExampleRow(
                municipality_code=code,
                municipality_name=names.get(code, code),
                target_year=target_year,
                target=abstention_pct(target_obs) if target_obs is not None else None,
                target_known_count=(target_obs.sv + target_obs.nv)
                if target_obs is not None
                else 0,
                features=features,
                origins=origins,
            )
        )

    return FeatureDataset(
        target_year=target_year,
        rows=tuple(rows),
        exclusions=tuple(exclusions),
        feature_order=FEATURE_ORDER,
    )


__all__ = [
    "FEATURE_ORDER",
    "ExampleRow",
    "Exclusion",
    "FeatureDataset",
    "abstention_pct",
    "build_examples",
    "is_midterm_election",
]
