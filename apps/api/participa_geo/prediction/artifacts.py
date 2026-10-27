"""Prediction records and artifact serialization (no pickle/joblib).

The five artifacts (``model.json``, ``evaluation.json``,
``predictions-2027.parquet``, ``exclusions.csv``, ``manifest.json``) are written
atomically (temp file + ``os.replace``). ``model_run_id`` is a deterministic
``uuid5`` over the model's content so re-runs never mint a fresh UUID.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pandas as pd

from participa_geo.indicators.calculations import QualityDecision
from participa_geo.prediction.cohorts import Exclusion
from participa_geo.prediction.risk import RiskLevel


@dataclass(frozen=True)
class PredictionRecord:
    """One municipality's forecast (or insufficient status) for 2027."""

    territory_id: UUID
    municipality_code: str
    municipality_name: str
    target_year: int
    estimated_abstention_pct: float | None
    historical_error_lower_pct: float | None
    historical_error_upper_pct: float | None
    risk: RiskLevel
    risk_unstable: bool
    eligible: bool
    quality: QualityDecision
    pre_clip_abstention_pct: float | None
    model_run_id: UUID


@dataclass(frozen=True)
class ModelBundle:
    """Everything produced by one training run, plus the serialized payloads."""

    model_run_id: UUID
    family: str
    target_year: int
    predictions: tuple[PredictionRecord, ...]
    exclusions: tuple[Exclusion, ...]
    candidate_count: int
    total_count: int
    model_payload: dict
    evaluation_payload: dict
    manifest_payload: dict
    data_aggregate_sha256: str


def compute_model_run_id(identity: Mapping) -> UUID:
    """Deterministic ``uuid5`` over a canonical model identity."""
    canonical = json.dumps(dict(identity), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return uuid5(NAMESPACE_URL, f"participa-geo:model:{digest}")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _quality_dict(quality: QualityDecision) -> dict:
    return {
        "eligible": quality.eligible,
        "reasons": list(quality.reasons),
        "identity_status": (
            quality.identity_status.value if quality.identity_status else None
        ),
        "footprint_status": (
            quality.footprint_status.value if quality.footprint_status else None
        ),
    }


def _predictions_frame(records) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "territory_id": pd.array([str(r.territory_id) for r in records], dtype="string"),
            "municipality_code": pd.array([r.municipality_code for r in records], dtype="string"),
            "municipality_name": pd.array([r.municipality_name for r in records], dtype="string"),
            "target_year": pd.array([r.target_year for r in records], dtype="int64"),
            "estimated_abstention_pct": pd.array(
                [r.estimated_abstention_pct for r in records], dtype="Float64"
            ),
            "historical_error_lower_pct": pd.array(
                [r.historical_error_lower_pct for r in records], dtype="Float64"
            ),
            "historical_error_upper_pct": pd.array(
                [r.historical_error_upper_pct for r in records], dtype="Float64"
            ),
            "pre_clip_abstention_pct": pd.array(
                [r.pre_clip_abstention_pct for r in records], dtype="Float64"
            ),
            "risk": pd.array([r.risk for r in records], dtype="string"),
            "risk_unstable": pd.array([r.risk_unstable for r in records], dtype="boolean"),
            "eligible": pd.array([r.eligible for r in records], dtype="boolean"),
            "identity_status": pd.array(
                [r.quality.identity_status.value if r.quality.identity_status else None
                 for r in records],
                dtype="string",
            ),
            "footprint_status": pd.array(
                [r.quality.footprint_status.value if r.quality.footprint_status else None
                 for r in records],
                dtype="string",
            ),
            "quality_reasons": pd.array(
                [";".join(r.quality.reasons) for r in records], dtype="string"
            ),
            "quality": pd.array(
                [json.dumps(_quality_dict(r.quality), sort_keys=True) for r in records],
                dtype="string",
            ),
            "model_run_id": pd.array([str(r.model_run_id) for r in records], dtype="string"),
        }
    )


def _write_parquet(path: Path, frame: pd.DataFrame) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        frame.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    except BaseException:
        if tmp.exists():
            os.unlink(tmp)
        raise


def write_artifacts(bundle: ModelBundle, output_dir: Path) -> None:
    """Write the five artifacts atomically and finalize the manifest hashes."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_bytes = json.dumps(
        bundle.model_payload, indent=2, sort_keys=True
    ).encode("utf-8")
    _atomic_write_bytes(output_dir / "model.json", model_bytes)

    evaluation_bytes = json.dumps(
        bundle.evaluation_payload, indent=2, sort_keys=True
    ).encode("utf-8")
    _atomic_write_bytes(output_dir / "evaluation.json", evaluation_bytes)

    frame = _predictions_frame(bundle.predictions)
    _write_parquet(output_dir / "predictions-2027.parquet", frame)

    exclusions_bytes = _exclusions_csv_bytes(bundle.exclusions)
    _atomic_write_bytes(output_dir / "exclusions.csv", exclusions_bytes)

    manifest_payload = dict(bundle.manifest_payload)
    manifest_payload["artifacts"] = {
        "model.json": {
            "sha256": _sha256_bytes(model_bytes),
            "bytes": len(model_bytes),
        },
        "evaluation.json": {
            "sha256": _sha256_bytes(evaluation_bytes),
            "bytes": len(evaluation_bytes),
        },
        "predictions-2027.parquet": {
            "sha256": _sha256_bytes((output_dir / "predictions-2027.parquet").read_bytes()),
            "bytes": (output_dir / "predictions-2027.parquet").stat().st_size,
        },
        "exclusions.csv": {
            "sha256": _sha256_bytes(exclusions_bytes),
            "bytes": len(exclusions_bytes),
        },
    }
    manifest_payload["generated_at"] = _now_utc_iso()
    manifest_bytes = json.dumps(manifest_payload, indent=2, sort_keys=True).encode("utf-8")
    _atomic_write_bytes(output_dir / "manifest.json", manifest_bytes)


def _now_utc_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def _exclusions_csv_bytes(exclusions) -> bytes:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["municipality_code", "municipality_name", "identity_status",
         "footprint_status", "reasons"]
    )
    for exclusion in exclusions:
        writer.writerow(
            [
                exclusion.municipality_code,
                exclusion.municipality_name,
                exclusion.identity_status.value if exclusion.identity_status else "",
                exclusion.footprint_status.value if exclusion.footprint_status else "",
                ";".join(exclusion.reasons),
            ]
        )
    return buffer.getvalue().encode("utf-8")


__all__ = [
    "ModelBundle",
    "PredictionRecord",
    "compute_model_run_id",
    "write_artifacts",
]
