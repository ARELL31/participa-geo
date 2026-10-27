"""Ingestion pipeline: read, validate, aggregate and persist official CCPC data.

Deterministic and idempotent: identical inputs produce identical aggregates and
the same logical content hash. All artifacts are written atomically (temp file +
``os.replace``) after the sources pass SHA-256 verification. The pipeline never
depends on ``/tmp`` and never publishes GIS or trains a model.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from participa_geo.indicators.calculations import assess_quality, calculate_indicators
from participa_geo.ingestion.aggregate import aggregate_municipal
from participa_geo.ingestion.schema import (
    JALISCO_STATE_CODE,
    CCPCRow,
    SourceManifest,
    observation_id,
    territory_id,
)
from participa_geo.ingestion.source import fetch_source, read_ccpc, verify_csv_sha256

#: Column order of the persisted observations (stable, no list columns).
COLUMNS = [
    "year",
    "state_code",
    "municipality_code",
    "municipality_name",
    "ln",
    "sv",
    "nv",
    "ns",
    "young_share",
    "senior_share",
    "rural_share",
    "participation_pct",
    "abstention_pct",
    "unknown_share",
    "ns_lower_pct",
    "ns_upper_pct",
    "eligible",
    "source_version_id",
    "observation_id",
    "territory_id",
]

_INT_COLUMNS = ["year", "ln", "sv", "nv", "ns"]
_FLOAT_COLUMNS = [
    "young_share",
    "senior_share",
    "rural_share",
    "participation_pct",
    "abstention_pct",
    "unknown_share",
    "ns_lower_pct",
    "ns_upper_pct",
]
_STRING_COLUMNS = [
    "state_code",
    "municipality_code",
    "municipality_name",
    "source_version_id",
    "observation_id",
    "territory_id",
]


@dataclass(frozen=True)
class IngestResult:
    observation_count: int
    aggregate_sha256: str
    sources: list[dict]


def _load_manifests(sources_path: Path) -> list[SourceManifest]:
    raw = json.loads(sources_path.read_text())
    manifests = [
        SourceManifest(
            year=entry["year"],
            source_url=entry["source_url"],
            member=entry["member"],
            sha256=entry["sha256"],
            encoding=entry.get("encoding", "utf-8-sig"),
            available_at=entry.get("available_at"),
        )
        for entry in raw["sources"]
    ]
    manifests.sort(key=lambda m: m.year)
    return manifests


def _atomic_write_text(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _atomic_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    os.close(fd)
    try:
        os.chmod(tmp, 0o644)
        frame.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _aggregate_sha256(records: list[dict]) -> str:
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_ingest(
    source_dir: Path,
    output_dir: Path,
    *,
    sources: Path | None = None,
    fetch: bool = False,
) -> IngestResult:
    """Read verified CSVs, aggregate municipally and persist the three artifacts.

    Returns an :class:`IngestResult` with the observation count, the logical
    aggregate SHA-256 and the per-source provenance records.
    """
    sources_path = sources or (Path.cwd() / "data" / "sources.json")
    manifests = _load_manifests(sources_path)
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []
    quality_records: list[dict] = []
    provenance_sources: list[dict] = []

    for manifest in manifests:
        csv_path = source_dir / manifest.file_name
        if not csv_path.exists():
            if not fetch:
                raise FileNotFoundError(
                    f"{csv_path} is missing; run with --fetch to obtain verified "
                    f"sources (or copy the verified CSV into {source_dir})."
                )
            csv_path = fetch_source(manifest, source_dir)
        verify_csv_sha256(csv_path, manifest.sha256)

        stats = {"rows": 0, "blank_del": 0, "blank_def": 0}

        def tracked(
            rows: Iterable[CCPCRow], _stats: dict[str, int] = stats
        ) -> Iterable[CCPCRow]:
            for row in rows:
                _stats["rows"] += 1
                if row.local_district is None:
                    _stats["blank_del"] += 1
                if row.federal_district is None:
                    _stats["blank_def"] += 1
                yield row

        observations = aggregate_municipal(tracked(read_ccpc(csv_path, manifest.year)))
        for obs in observations:
            obs.source_version_id = manifest.version_id
            indicators = calculate_indicators(obs.ln, obs.sv, obs.nv, obs.ns)
            quality = assess_quality(obs)
            record = {
                "year": obs.year,
                "state_code": obs.key.state_code,
                "municipality_code": obs.key.municipality_code,
                "municipality_name": obs.municipality_name,
                "ln": obs.ln,
                "sv": obs.sv,
                "nv": obs.nv,
                "ns": obs.ns,
                "young_share": obs.young_share,
                "senior_share": obs.senior_share,
                "rural_share": obs.rural_share,
                "participation_pct": indicators.participation_pct,
                "abstention_pct": indicators.abstention_pct,
                "unknown_share": indicators.unknown_share,
                "ns_lower_pct": indicators.ns_lower_pct,
                "ns_upper_pct": indicators.ns_upper_pct,
                "eligible": quality.eligible,
                "source_version_id": str(obs.source_version_id),
                "observation_id": str(
                    observation_id(obs.key.state_code, obs.key.municipality_code, obs.year)
                ),
                "territory_id": str(
                    territory_id(obs.key.state_code, obs.key.municipality_code)
                ),
            }
            all_records.append(record)
            quality_records.append(
                {
                    "year": obs.year,
                    "municipality_code": obs.key.municipality_code,
                    "eligible": quality.eligible,
                    "reasons": quality.reasons,
                    "identity_status": None,
                    "footprint_status": None,
                }
            )

        year_totals = {
            "ln": sum(o.ln for o in observations),
            "sv": sum(o.sv for o in observations),
            "nv": sum(o.nv for o in observations),
            "ns": sum(o.ns for o in observations),
        }
        provenance_sources.append(
            {
                "year": manifest.year,
                "source_url": manifest.source_url,
                "member": manifest.member,
                "sha256": manifest.sha256,
                "available_at": manifest.available_at.isoformat()
                if manifest.available_at
                else None,
                "source_row_count": stats["rows"],
                "blank_del_count": stats["blank_del"],
                "blank_def_count": stats["blank_def"],
                "municipality_count": len(observations),
                "totals": year_totals,
                "source_version_id": str(manifest.version_id),
            }
        )

    all_records.sort(key=lambda r: (r["year"], r["municipality_code"]))
    quality_records.sort(key=lambda r: (r["year"], r["municipality_code"]))
    aggregate_hash = _aggregate_sha256(all_records)

    frame = pd.DataFrame(all_records, columns=COLUMNS)
    frame = frame.astype({c: "int64" for c in _INT_COLUMNS})
    frame = frame.astype({c: "Float64" for c in _FLOAT_COLUMNS})
    frame = frame.astype({c: "string" for c in _STRING_COLUMNS})
    frame = frame.astype({"eligible": "boolean"})

    provenance = {
        "generated_at": datetime.now(UTC).isoformat(),
        "state_code": JALISCO_STATE_CODE,
        "aggregate_sha256": aggregate_hash,
        "observation_count": len(all_records),
        "sources": provenance_sources,
    }

    _atomic_write_parquet(output_dir / "municipal-observations.parquet", frame)
    _atomic_write_text(
        output_dir / "quality.json",
        json.dumps(quality_records, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    _atomic_write_text(
        output_dir / "provenance.json",
        json.dumps(provenance, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )

    return IngestResult(
        observation_count=len(all_records),
        aggregate_sha256=aggregate_hash,
        sources=provenance_sources,
    )


__all__ = ["IngestResult", "run_ingest"]
