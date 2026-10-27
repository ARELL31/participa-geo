"""Cohort construction and territorial identity statuses.

A municipality enters a cohort for target ``t`` only when its catalogue identity
is ``verified_catalogue`` (footprint ``known_changed`` also excludes it) and the
required quality rule holds at every required year. For a retrospective target
that is ``t``, ``t-3`` and ``t-6``; for 2027 only the antecedents 2021 and 2024
exist. Identity statuses come from PostGIS (T3); they are never assumed, and a
municipality missing from the mapping raises loudly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from participa_geo.indicators.calculations import assess_quality
from participa_geo.ingestion.schema import (
    REFERENCE_DATE,
    FootprintStatus,
    IdentityStatus,
)

#: The forecast horizon fixed for this MVP (Spec §7).
TARGET_YEAR = 2027

#: The six CCPC election years (one correspondence each per municipality).
EXPECTED_CORRESPONDENCES = 6
EXPECTED_MUNICIPALITIES = 125


class IncompleteIdentityError(RuntimeError):
    """Raised when identity statuses cannot be read completely from PostGIS."""


@dataclass(frozen=True)
class TerritoryIdentity:
    """Identity and footprint status for one municipality (T3)."""

    identity_status: IdentityStatus
    footprint_status: FootprintStatus


@dataclass(frozen=True)
class Exclusion:
    """A municipality excluded from a cohort, with its stable reasons."""

    municipality_code: str
    municipality_name: str
    reasons: tuple[str, ...]
    identity_status: IdentityStatus | None
    footprint_status: FootprintStatus | None


def required_quality_years(target_year: int) -> tuple[int, ...]:
    """Years whose quality is required for a cohort (target and antecedents)."""
    if target_year == TARGET_YEAR:
        return (target_year - 6, target_year - 3)
    return (target_year, target_year - 3, target_year - 6)


def identity_reasons(ident: TerritoryIdentity) -> list[str]:
    """Stable exclusion reasons for a non-verified or changed territory."""
    reasons: list[str] = []
    if ident.identity_status == IdentityStatus.ambiguous:
        reasons.append("ambiguous_identity")
    elif ident.identity_status == IdentityStatus.known_changed:
        reasons.append("known_administrative_change")
    elif ident.identity_status != IdentityStatus.verified_catalogue:
        reasons.append("ambiguous_identity")
    if ident.footprint_status == FootprintStatus.known_changed:
        reasons.append("known_administrative_change")
    return reasons


def build_cohort(
    observations,
    target_year: int,
    identity_statuses: Mapping[str, TerritoryIdentity],
) -> tuple[list[str], list[Exclusion]]:
    """Return ``(eligible_codes, exclusions)`` for ``target_year``."""
    observations = list(observations)
    index = {
        (obs.key.municipality_code, obs.year): obs for obs in observations
    }
    all_codes = sorted({obs.key.municipality_code for obs in observations})
    names = {obs.key.municipality_code: obs.municipality_name for obs in observations}
    required = required_quality_years(target_year)

    eligible: list[str] = []
    exclusions: list[Exclusion] = []
    for code in all_codes:
        ident = identity_statuses.get(code)
        if ident is None:
            raise IncompleteIdentityError(
                f"missing identity status for municipality {code}; "
                "refusing to assume verified"
            )

        reasons = list(identity_reasons(ident))
        for year in required:
            obs = index.get((code, year))
            if obs is None:
                reasons.append("missing_lag")
                continue
            decision = assess_quality(obs)
            if not decision.eligible:
                reasons.extend(decision.reasons)

        reasons = _dedupe(reasons)
        if reasons:
            exclusions.append(
                Exclusion(
                    municipality_code=code,
                    municipality_name=names.get(code, code),
                    reasons=tuple(reasons),
                    identity_status=ident.identity_status,
                    footprint_status=ident.footprint_status,
                )
            )
        else:
            eligible.append(code)

    return sorted(eligible), exclusions


def read_identity_statuses(session: Session) -> dict[str, TerritoryIdentity]:
    """Read identity/footprint statuses for the 2025 reference from PostGIS.

    Fails loudly (never assumes verified) when the catalogue is incomplete or a
    municipality has inconsistent or missing statuses.
    """
    rows = session.execute(
        text(
            """
            SELECT t.municipality_code, c.identity_status, c.footprint_status
            FROM territory_version t
            JOIN territory_correspondence c ON c.reference_territory_id = t.id
            WHERE t.reference_date = :ref_date
            """
        ),
        {"ref_date": date.fromisoformat(REFERENCE_DATE)},
    ).all()

    counts: dict[str, int] = {}
    pairs: dict[str, set[tuple[str, str]]] = {}
    for code, identity_status, footprint_status in rows:
        counts[code] = counts.get(code, 0) + 1
        pairs.setdefault(code, set()).add((identity_status, footprint_status))

    if len(counts) != EXPECTED_MUNICIPALITIES:
        raise IncompleteIdentityError(
            f"expected {EXPECTED_MUNICIPALITIES} municipalities with identity "
            f"statuses, found {len(counts)}"
        )

    result: dict[str, TerritoryIdentity] = {}
    for code in sorted(counts):
        if counts[code] != EXPECTED_CORRESPONDENCES:
            raise IncompleteIdentityError(
                f"municipality {code} has {counts[code]} correspondences, "
                f"expected {EXPECTED_CORRESPONDENCES}"
            )
        statuses = pairs[code]
        if len(statuses) != 1:
            raise IncompleteIdentityError(
                f"municipality {code} has inconsistent identity statuses: {statuses}"
            )
        identity_status, footprint_status = next(iter(statuses))
        result[code] = TerritoryIdentity(
            IdentityStatus(identity_status), FootprintStatus(footprint_status)
        )

    return result


def _dedupe(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            out.append(reason)
    return out


__all__ = [
    "EXPECTED_MUNICIPALITIES",
    "Exclusion",
    "IncompleteIdentityError",
    "TARGET_YEAR",
    "TerritoryIdentity",
    "build_cohort",
    "identity_reasons",
    "read_identity_statuses",
    "required_quality_years",
]
