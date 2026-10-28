"""Scenario GeoJSON: the verified INE 2025 reference plus persisted A/B values.

The geometry is copied byte-for-value from the processed 2025-12-15 reference
(EPSG:4326, 125 municipalities). No polygon is invented, simplified or
re-projected. Insufficient municipalities keep ``null`` values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from participa_geo.api.schemas.common import DatasetMeta
from participa_geo.api.schemas.reports import REPORT_RULES_VERSION
from participa_geo.api.schemas.scenarios import ScenarioDTO
from participa_geo.territory import TerritoryKey, territory_id

_GEOMETRY_TYPES = frozenset({"Polygon", "MultiPolygon"})


class GeoJSONExportError(RuntimeError):
    """Raised when the reference or scenario cannot produce a valid export."""


def _positions(geometry: dict[str, Any]):
    if geometry.get("type") == "Polygon":
        rings = geometry.get("coordinates", [])
    elif geometry.get("type") == "MultiPolygon":
        rings = [
            ring
            for polygon in geometry.get("coordinates", [])
            for ring in polygon
        ]
    else:
        raise GeoJSONExportError(
            f"geometría no admitida: {geometry.get('type')!r}"
        )
    if not rings:
        raise GeoJSONExportError("geometría vacía")
    for ring in rings:
        for position in ring:
            if not isinstance(position, (list, tuple)) or len(position) < 2:
                raise GeoJSONExportError("posición inválida")
            x, y = position[0], position[1]
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise GeoJSONExportError("coordenada no numérica")
            if not (-180.0 <= float(x) <= 180.0 and -90.0 <= float(y) <= 90.0):
                raise GeoJSONExportError(
                    "coordenada fuera de EPSG:4326; no se rotula una geometría UTM como lon/lat"
                )


def load_reference(path: Path) -> dict[str, dict[str, Any]]:
    """Read and validate the 125-feature 2025 reference keyed by municipality code."""
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GeoJSONExportError("no se pudo leer la referencia cartográfica") from exc
    if body.get("type") != "FeatureCollection":
        raise GeoJSONExportError("la referencia no es una FeatureCollection")
    features = body.get("features")
    if not isinstance(features, list) or len(features) != 125:
        raise GeoJSONExportError("la referencia debe contener 125 municipios")
    if body.get("crs") is not None:
        raise GeoJSONExportError("la referencia debe usar EPSG:4326 sin objeto crs (RFC 7946)")
    by_code: dict[str, dict[str, Any]] = {}
    for feature in features:
        properties = feature.get("properties") or {}
        raw_code = properties.get("municipio")
        if raw_code is None:
            raise GeoJSONExportError("la referencia no contiene código municipal")
        code = str(int(raw_code)).zfill(3)
        if code in by_code:
            raise GeoJSONExportError(f"código municipal duplicado: {code}")
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in _GEOMETRY_TYPES:
            raise GeoJSONExportError(f"geometría no admitida para {code}")
        _positions(geometry)
        by_code[code] = feature
    if len(by_code) != 125:
        raise GeoJSONExportError("la referencia no contiene 125 códigos únicos")
    return by_code


def export_scenario_geojson(
    scenario: ScenarioDTO,
    reference_path: Path,
    meta: DatasetMeta,
    *,
    sources: dict | None = None,
) -> bytes:
    """Build the bounded reference GeoJSON using persisted A/B values.

    Scenarios persist the full national cohort, while the verified geometry
    reference currently covers Jalisco only. Match the reference features to
    their state-scoped stable territory IDs and export that supported subset.
    """
    reference = load_reference(reference_path)
    results = {result.territory_id: result for result in scenario.results}
    reference_results: dict[str, Any] = {}
    for code, feature in reference.items():
        properties = feature.get("properties") or {}
        state_code = str(properties.get("entidad", "14")).zfill(2)
        reference_id = territory_id(
            TerritoryKey("municipality", state_code, code)
        )
        result = results.get(reference_id)
        if result is not None:
            reference_results[code] = result
    if set(reference_results) != set(reference):
        missing = sorted(set(reference) - set(reference_results))
        raise GeoJSONExportError(
            f"la referencia y el escenario no coinciden (faltan={missing[:5]})"
        )

    features: list[dict[str, Any]] = []
    for code in sorted(reference):
        original = reference[code]
        result = reference_results[code]
        baseline = result.baseline_abstention_pct
        hypothetical = (
            result.hypothetical_abstention_pct if baseline is not None else None
        )
        properties = {
            **(original.get("properties") or {}),
            "territory_id": str(result.territory_id),
            "municipality_code": code,
            "municipality_name": result.municipality_name,
            "scenario_id": str(scenario.scenario_id),
            "target_year": scenario.target_year,
            "selected": bool(result.selected and baseline is not None),
            "baseline_abstention_pct": baseline,
            "hypothetical_abstention_pct": hypothetical,
            "baseline_error_lower_pct": result.baseline_error_lower_pct,
            "baseline_error_upper_pct": result.baseline_error_upper_pct,
            "hypothetical_error_lower_pct": (
                result.hypothetical_error_lower_pct if baseline is not None else None
            ),
            "hypothetical_error_upper_pct": (
                result.hypothetical_error_upper_pct if baseline is not None else None
            ),
            "requested_reduction_pp": result.requested_reduction_pp,
            "effective_reduction_pp": (
                result.effective_reduction_pp if baseline is not None else None
            ),
            "risk_a": result.risk_a if baseline is not None else "insufficient",
            "risk_b": (
                result.risk_b
                if (baseline is not None and hypothetical is not None)
                else "insufficient"
            ),
            "risk_a_unstable": bool(result.risk_a_unstable and baseline is not None),
            "risk_b_unstable": bool(
                result.risk_b_unstable and baseline is not None and hypothetical is not None
            ),
            "reference_date": meta.reference_date,
            "assumption_code": scenario.assumption_code,
            "assumption_version": scenario.assumption_version,
            "rules_version": scenario.rules_version,
            "error_band_label": scenario.error_band_label,
        }
        features.append(
            {
                "type": "Feature",
                "id": code,
                "geometry": original["geometry"],
                "properties": properties,
            }
        )

    body = {
        "type": "FeatureCollection",
        "metadata": {
            "title": "PARTICIPA-GEO · escenario municipal hipotético 2027",
            "scenario_id": str(scenario.scenario_id),
            "model_run_id": str(scenario.model_run_id),
            "model_sha256": scenario.model_sha256,
            "input_sha256": scenario.input_sha256,
            "dataset_version_ids": [
                str(item) for item in meta.dataset_version_ids
            ],
            "report_kind": meta.filters.get("report_kind"),
            "target_year": scenario.target_year,
            "reference_date": meta.reference_date,
            "crs": "EPSG:4326",
            "generated_at": meta.generated_at.isoformat(),
            "geographic_warning": meta.geographic_warning,
            "assumption_code": scenario.assumption_code,
            "assumption_version": scenario.assumption_version,
            "rationale_text": scenario.rationale_text,
            "rules_version": scenario.rules_version,
            "report_rules_version": REPORT_RULES_VERSION,
            "error_band_label": scenario.error_band_label,
            "sources": sources or {},
            "notice": (
                "Agregados municipales; prohibida la inferencia individual. "
                "El escenario es hipotético y no implica efecto causal."
            ),
        },
        "features": features,
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


__all__ = [
    "GeoJSONExportError",
    "export_scenario_geojson",
    "load_reference",
]
