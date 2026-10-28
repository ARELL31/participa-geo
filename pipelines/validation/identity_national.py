"""Build national municipal identities from Task 4 MGS and municipal CCPC rows."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.orm import Session

from participa_geo.ingestion.schema import MunicipalObservation, observation_id
from participa_geo.territory import TerritoryKey, territory_id

REFERENCE_DATE = date(2025, 12, 15)
EXPECTED_MUNICIPALITIES = 2477
STATE_CODES = {f"{state:02d}" for state in range(1, 33)}


class NationalIdentityError(RuntimeError):
    """National MGS/catalog identity evidence is incomplete or ambiguous."""


@dataclass(frozen=True)
class NationalIdentityAudit:
    reference_count: int
    origin_count: int
    correspondence_count: int
    verified_count: int
    ambiguous_count: int


def build_national_municipal_identity(
    session: Session,
    observations: list[MunicipalObservation],
) -> NationalIdentityAudit:
    """Idempotently write reference, origin, and code+entity correspondence rows.

    Reference geometry and identity universe come exclusively from Task 4's
    ``geo_municipality`` layer. No district bridge participates in municipal
    identity resolution. Historical names are provenance only; matching is by
    normalized entity and municipal code.
    """
    refs = session.execute(
        text("""
            SELECT state_code, municipality_code, name, ST_AsBinary(geom) AS geometry_wkb,
                   ST_SRID(geom) AS srid, provenance
            FROM geo_municipality
            ORDER BY state_code, municipality_code
        """)
    ).all()
    return persist_national_municipal_identity(session, observations, refs)


def persist_national_municipal_identity(
    session: Session,
    observations: list[MunicipalObservation],
    mgs_references,
) -> NationalIdentityAudit:
    """Persist using validated MGS municipality records; separately testable."""
    reference_by_key: dict[tuple[str, str], tuple] = {}
    states: set[str] = set()
    for row in mgs_references:
        state, code = str(row[0]), str(row[1])
        key = (state, code)
        if key in reference_by_key:
            raise NationalIdentityError(f"duplicate MGS municipality identity: {key}")
        if state not in STATE_CODES or not re.fullmatch(r"\d{3}", code) or code == "000":
            raise NationalIdentityError(f"invalid MGS municipality key: {key}")
        if row[3] is None or int(row[4]) != 4326:
            raise NationalIdentityError(
                f"MGS municipality geometry is missing/not EPSG:4326: {key}"
            )
        reference_by_key[key] = row
        states.add(state)
    if len(reference_by_key) != EXPECTED_MUNICIPALITIES or states != STATE_CODES:
        raise NationalIdentityError(
            f"incomplete MGS municipality reference: {len(reference_by_key)}/"
            f"{EXPECTED_MUNICIPALITIES} municipalities across {len(states)}/32 states"
        )

    if len({(o.key.state_code, o.key.municipality_code, o.year) for o in observations}) != len(
        observations
    ):
        raise NationalIdentityError("duplicate national municipal observation key/year")

    ref_ids: dict[tuple[str, str], UUID] = {}
    for key, row in sorted(reference_by_key.items()):
        state, code, name, wkb, _, source_provenance = row
        ref_id = territory_id(TerritoryKey("municipality", state, code))
        ref_ids[key] = ref_id
        session.execute(
            text("""
                INSERT INTO territory_version
                    (id, system, state_code, level, territory_code, municipality_code,
                     district_plan, name, reference_date, origin_year, geometry,
                     source_srid, provenance)
                VALUES (:id, 'ine', :state, 'municipality', :code, :code, NULL,
                        :name, :reference_date, NULL, ST_SetSRID(ST_GeomFromWKB(:wkb),4326),
                        :source_srid, :provenance)
                ON CONFLICT (id) DO UPDATE SET
                    state_code=EXCLUDED.state_code, level=EXCLUDED.level,
                    territory_code=EXCLUDED.territory_code,
                    municipality_code=EXCLUDED.municipality_code, district_plan=NULL,
                    name=EXCLUDED.name, reference_date=EXCLUDED.reference_date,
                    origin_year=NULL, geometry=EXCLUDED.geometry,
                    source_srid=EXCLUDED.source_srid,
                    provenance=EXCLUDED.provenance
            """),
            {
                "id": ref_id,
                "state": state,
                "code": code,
                "name": name,
                "reference_date": REFERENCE_DATE,
                "wkb": wkb,
                "source_srid": 4326,
                "provenance": f"{source_provenance}; municipal identity by state+code",
            },
        )

    verified = ambiguous = 0
    correspondence_count = 0
    for obs in sorted(
        observations, key=lambda item: (item.key.state_code, item.key.municipality_code, item.year)
    ):
        state, code = obs.key.state_code, obs.key.municipality_code
        source_id = obs.source_version_id
        if source_id is None:
            raise NationalIdentityError(
                f"missing dataset version for observation {state}/{code}/{obs.year}"
            )
        origin_key = (state, code)
        valid_code = state in STATE_CODES and bool(re.fullmatch(r"\d{3}", code)) and code != "000"
        ref_id = ref_ids.get(origin_key) if valid_code else None
        identity_status = "verified_catalogue" if ref_id is not None else "ambiguous"
        evidence = {
            "source": "INE MGS 2025-12-15",
            "method": "exact state_code + municipality_code; name not used",
            "origin_year": obs.year,
            "dataset_version_id": str(source_id),
            "valid_municipal_code": valid_code,
            "mgs_reference_match": ref_id is not None,
        }
        origin_id = observation_id(state, code, obs.year, source_id)
        session.execute(
            text("""
                INSERT INTO territory_version
                    (id, system, state_code, level, territory_code, municipality_code,
                     district_plan, name, reference_date, origin_year, geometry,
                     source_srid, provenance)
                VALUES (:id, 'ine', :state, 'municipality', :code, :code, NULL,
                        :name, NULL, :year, NULL, NULL, :provenance)
                ON CONFLICT (id) DO UPDATE SET
                    state_code=EXCLUDED.state_code, level=EXCLUDED.level,
                    territory_code=EXCLUDED.territory_code,
                    municipality_code=EXCLUDED.municipality_code, district_plan=NULL,
                    name=EXCLUDED.name, reference_date=NULL,
                    origin_year=EXCLUDED.origin_year, geometry=NULL, source_srid=NULL,
                    provenance=EXCLUDED.provenance
            """),
            {
                "id": origin_id,
                "state": state,
                "code": code,
                "name": obs.municipality_name,
                "year": obs.year,
                "provenance": f"CCPC national municipal aggregate {obs.year}; dataset={source_id}",
            },
        )
        correspondence_id = uuid5(
            NAMESPACE_URL,
            f"correspondence:{origin_id}:{ref_id if ref_id is not None else 'unmatched'}",
        )
        session.execute(
            text("""
                INSERT INTO territory_correspondence
                    (id, origin_territory_id, reference_territory_id, relation_type,
                     evidence, identity_status, footprint_status)
                VALUES (:id, :origin_id, :reference_id, :relation_type, CAST(:evidence AS jsonb),
                        :identity_status, :footprint_status)
                ON CONFLICT (id) DO UPDATE SET
                    origin_territory_id=EXCLUDED.origin_territory_id,
                    reference_territory_id=EXCLUDED.reference_territory_id,
                    relation_type=EXCLUDED.relation_type, evidence=EXCLUDED.evidence,
                    identity_status=EXCLUDED.identity_status,
                    footprint_status=EXCLUDED.footprint_status
            """),
            {
                "id": correspondence_id,
                "origin_id": origin_id,
                "reference_id": ref_id,
                "relation_type": "catalogue_match" if ref_id is not None else "unmatched_catalogue",
                "evidence": json.dumps(evidence, sort_keys=True),
                "identity_status": identity_status,
                "footprint_status": "not_verified",
            },
        )
        correspondence_count += 1
        if ref_id is None:
            ambiguous += 1
        else:
            verified += 1
    return NationalIdentityAudit(
        len(reference_by_key), len(observations), correspondence_count, verified, ambiguous
    )


__all__ = [
    "NationalIdentityAudit",
    "NationalIdentityError",
    "build_national_municipal_identity",
    "persist_national_municipal_identity",
]
