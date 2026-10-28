"""Load audited national municipal aggregates and train the 2027 model."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from participa_geo.ingestion.national import resolve_current_generation
from participa_geo.ingestion.schema import (
    FootprintStatus,
    IdentityStatus,
    MunicipalityKey,
    MunicipalObservation,
)
from participa_geo.prediction.cohorts import IncompleteIdentityError, TerritoryIdentity
from participa_geo.prediction.national import NationalModelBundle, train_national

EXPECTED_MUNICIPALITIES = 2477
EXPECTED_STATES = 32
MIN_CORRESPONDENCES = 1


def read_national_municipal_observations(processed_dir: Path) -> list[MunicipalObservation]:
    """Read the checksummed national ingestion generation, not MVP aggregates."""
    generation = resolve_current_generation(Path(processed_dir))
    manifest = json.loads((generation / "national-ingest.json").read_text())
    aggregate_path = generation / "municipal-observations.parquet"
    if not aggregate_path.is_file():
        raise FileNotFoundError(f"missing national municipal aggregate: {aggregate_path}")
    frame = pd.read_parquet(aggregate_path)
    expected = {
        "state_code",
        "municipality_code",
        "year",
        "ln",
        "sv",
        "nv",
        "ns",
        "municipality_name",
        "young_share",
        "senior_share",
        "rural_share",
    }
    if not expected.issubset(frame.columns):
        raise ValueError(
            f"national municipal aggregate missing columns: {sorted(expected - set(frame.columns))}"
        )
    out = [
        MunicipalObservation(
            key=MunicipalityKey(str(r.state_code), str(r.municipality_code)),
            year=int(r.year),
            ln=int(r.ln),
            sv=int(r.sv),
            nv=int(r.nv),
            ns=int(r.ns),
            municipality_name=str(r.municipality_name),
            young_share=_float_or_none(r.young_share),
            senior_share=_float_or_none(r.senior_share),
            rural_share=_float_or_none(r.rural_share),
        )
        for r in frame.itertuples(index=False)
    ]
    if len(out) != manifest.get("municipality_observation_count"):
        raise ValueError("national municipal aggregate row count does not match ingestion manifest")
    return out


def read_national_identity_statuses(session: Session) -> dict[tuple[str, str], TerritoryIdentity]:
    """Read and validate all municipal identity/footprint statuses from PostGIS."""
    rows = session.execute(
        text("""
        SELECT t.state_code, t.municipality_code,
               count(c.origin_territory_id) AS correspondence_count,
               count(DISTINCT (c.identity_status, c.footprint_status)) AS status_pairs,
               min(c.identity_status) AS identity_status,
               min(c.footprint_status) AS footprint_status
        FROM territory_version t
        LEFT JOIN territory_correspondence c ON c.reference_territory_id = t.id
        WHERE t.reference_date = DATE '2025-12-15'
          AND t.level = 'municipality'
        GROUP BY t.state_code, t.municipality_code
        ORDER BY t.state_code, t.municipality_code
    """)
    ).all()
    if not rows:
        raise IncompleteIdentityError("national municipality identity/coverage records are missing")
    result: dict[tuple[str, str], TerritoryIdentity] = {}
    bad = []
    states: set[str] = set()
    for state, code, count, status_pairs, identity, footprint in rows:
        key = (str(state), str(code))
        states.add(key[0])
        if (
            count < MIN_CORRESPONDENCES
            or status_pairs != 1
            or identity is None
            or footprint is None
        ):
            bad.append((key, count, status_pairs))
            continue
        result[key] = TerritoryIdentity(IdentityStatus(identity), FootprintStatus(footprint))
    if len(rows) != EXPECTED_MUNICIPALITIES or len(states) != EXPECTED_STATES or bad:
        raise IncompleteIdentityError(
            "national identity/coverage incomplete: "
            f"municipalities={len(rows)}/{EXPECTED_MUNICIPALITIES}, "
            f"states={len(states)}/{EXPECTED_STATES}, invalid={bad[:10]}"
        )
    return result


def train_national_municipal(
    processed_dir: Path, output_dir: Path, session: Session
) -> NationalModelBundle:
    observations = read_national_municipal_observations(processed_dir)
    identities = read_national_identity_statuses(session)
    return train_national(
        observations,
        level="municipality",
        output_dir=output_dir,
        identity_statuses=identities,
        universe=tuple(identities),
    )


def _float_or_none(value) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


__all__ = [
    "read_national_identity_statuses",
    "read_national_municipal_observations",
    "train_national_municipal",
]
