"""National report helpers and observed district fiche generation."""

from __future__ import annotations

import io
import json
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from participa_geo.api.schemas.common import DatasetMeta
from participa_geo.api.schemas.history import HistoryDTO


def generate_district_observed_fiche(record: HistoryDTO) -> bytes:
    """Build a single-district 2024 fiche from the persisted observation DTO."""
    if record.level != "federal_district" or record.year != 2024:
        raise ValueError("la ficha distrital sólo acepta observaciones distritales 2024")
    return generate_observed_territory_fiche(record)


def generate_observed_territory_fiche(record: HistoryDTO) -> bytes:
    """Build a state/municipality/district observed-2024 profile without forecasts."""
    if record.year != 2024:
        raise ValueError("la ficha sólo acepta observaciones de 2024")
    level_name = {
        "municipality": "municipio / agregado estatal",
        "federal_district": "distrito federal",
    }[record.level]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Ficha observada 2024 · {record.name or record.territory_code}",
        author="PARTICIPA-GEO",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"PARTICIPA-GEO · Ficha {level_name}", styles["Title"]),
        Paragraph(
            "Observado 2024 · Plan DERFE2023"
            if record.level == "federal_district"
            else "Observado 2024 · referencia municipal nacional",
            styles["Heading2"],
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            "Perfil descriptivo basado en conteos observados. No contiene predicción, "
            "banda de incertidumbre predictiva ni escenarios.",
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
        Table(
            [
                ["Indicador", "Valor"],
                ["Distrito", record.name or record.territory_code or ""],
                ["Año observado", "2024"],
                ["Plan", record.district_plan or "DERFE2023"],
                ["Lista nominal (LN)", f"{record.ln:,}"],
                ["Votación (SV)", f"{record.sv:,}"],
                ["No votó (NV)", f"{record.nv:,}"],
                ["No especificado (NS)", f"{record.ns:,}"],
                [
                    "Abstención observada",
                    "—" if record.abstention_pct is None else f"{record.abstention_pct:.2f}%",
                ],
                [
                    "Cobertura de reconstrucción",
                    "No disponible"
                    if record.coverage_share is None
                    else f"{record.coverage_share:.1%}",
                ],
            ],
            colWidths=[75 * mm, 85 * mm],
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            (
                "La cobertura describe la proporción de lista nominal 2024 conciliada con "
                "la correspondencia sección–distrito del plan publicado. No es cobertura "
                "de una predicción ni una medida de representatividad."
                if record.level == "federal_district"
                else "Los conteos son observados; no se estiman personas ni efectos causales."
            ),
            styles["BodyText"],
        ),
    ]
    table = story[5]
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7b1638")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d7d0d2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    doc.build(story)
    return buffer.getvalue()


def export_national_geojson(
    feature_collection: dict[str, Any],
    *,
    level: str,
    state_code: str,
    meta: DatasetMeta,
    observations: list[HistoryDTO] | None = None,
    sources: dict[str, Any] | None = None,
) -> bytes:
    """Export one state's real GeoServer features and observed district values."""
    if feature_collection.get("type") != "FeatureCollection":
        raise ValueError("GeoServer no devolvió una FeatureCollection")
    features = feature_collection.get("features")
    if not isinstance(features, list) or len(features) > 1000:
        raise ValueError("GeoJSON supera el límite de 1,000 geometrías por entidad")
    observed = {
        str(row.territory_code).zfill(2): row for row in (observations or []) if row.territory_code
    }
    exported = []
    for feature in features:
        geometry = feature.get("geometry")
        properties = dict(feature.get("properties") or {})
        if level == "federal_district":
            code = str(properties.get("district_code", "")).zfill(2)
            record = observed.get(code)
            properties.update(
                {
                    "district_plan": "DERFE2023",
                    "observed_year": 2024,
                    "observation_label": "Observado 2024",
                    "ln": record.ln if record else None,
                    "sv": record.sv if record else None,
                    "nv": record.nv if record else None,
                    "ns": record.ns if record else None,
                    "observed_abstention_pct": record.abstention_pct if record else None,
                    "coverage_share": record.coverage_share if record else None,
                }
            )
        properties.update({"level": level, "state_code": state_code})
        exported.append(
            {
                "type": "Feature",
                "id": feature.get("id"),
                "geometry": geometry,
                "properties": properties,
            }
        )
    body = {
        "type": "FeatureCollection",
        "metadata": {
            "title": "PARTICIPA-GEO · GeoJSON nacional por entidad y nivel",
            "level": level,
            "state_code": state_code,
            "district_plan": "DERFE2023" if level == "federal_district" else None,
            "observed_year": 2024 if level == "federal_district" else None,
            "model_run_id": str(meta.model_run_id) if meta.model_run_id else None,
            "dataset_version_ids": [str(item) for item in meta.dataset_version_ids],
            "reference_date": meta.reference_date,
            "generated_at": meta.generated_at.isoformat(),
            "sources": sources or {},
            "geographic_warning": meta.geographic_warning,
        },
        "features": exported,
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


__all__ = [
    "export_national_geojson",
    "generate_district_observed_fiche",
    "generate_observed_territory_fiche",
]
