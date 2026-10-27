"""Ingestion domain for PARTICIPA-GEO."""

from participa_geo.ingestion.aggregate import aggregate_municipal
from participa_geo.ingestion.schema import (
    CCPC_COLUMNS,
    CCPCRow,
    CCPCSchemaError,
    FootprintStatus,
    IdentityStatus,
    MunicipalityKey,
    MunicipalObservation,
    SourceManifest,
    dataset_version_id,
    observation_id,
    territory_id,
)
from participa_geo.ingestion.source import read_ccpc

__all__ = [
    "CCPC_COLUMNS",
    "CCPCRow",
    "CCPCSchemaError",
    "FootprintStatus",
    "IdentityStatus",
    "MunicipalObservation",
    "MunicipalityKey",
    "SourceManifest",
    "aggregate_municipal",
    "dataset_version_id",
    "observation_id",
    "read_ccpc",
    "territory_id",
]
