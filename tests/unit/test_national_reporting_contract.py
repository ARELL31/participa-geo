from __future__ import annotations

import io
import json

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from participa_geo.api.schemas.reports import ReportRequest
from participa_geo.reporting.delivery import load_delivery_context
from participa_geo.reporting.national import (
    export_national_geojson,
    generate_district_observed_fiche,
)
from participa_geo.reporting.pdf import generate_executive, generate_methodology


def test_report_request_carries_level_and_plan_metadata():
    request = ReportRequest(
        kind="history_csv", level="federal_district", district_plan="DERFE2023", year=2024
    )
    assert request.level == "federal_district"
    assert request.district_plan == "DERFE2023"


def test_district_observed_report_is_explicit_and_does_not_accept_2027():
    request = ReportRequest(
        kind="district_observed_pdf",
        level="federal_district",
        district_plan="DERFE2023",
        year=2024,
        territory_id="00000000-0000-0000-0000-000000000002",
    )
    assert request.year == 2024
    with pytest.raises(ValidationError):
        ReportRequest(
            kind="district_observed_pdf",
            level="federal_district",
            district_plan="DERFE2023",
            year=2027,
            territory_id="00000000-0000-0000-0000-000000000002",
        )


def test_district_scenario_report_is_rejected():
    with pytest.raises(ValidationError):
        ReportRequest(
            kind="scenario_csv",
            scenario_id="00000000-0000-0000-0000-000000000001",
            level="federal_district",
            district_plan="DERFE2023",
        )


def test_state_and_municipality_fiches_require_a_selected_state_and_2024():
    request = ReportRequest(
        kind="territory_fiche_pdf", level="municipality", state_code="14", year=2024
    )
    assert request.state_code == "14"
    with pytest.raises(ValidationError):
        ReportRequest(kind="territory_fiche_pdf", state_code="all", year=2024)
    with pytest.raises(ValidationError):
        ReportRequest(kind="territory_fiche_pdf", state_code="14", year=2027)


def test_national_geojson_scopes_state_and_district_features_to_observed_2024():
    from participa_geo.api.schemas.common import DatasetMeta
    from participa_geo.api.schemas.history import HistoryDTO

    output = export_national_geojson(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "district.1401",
                    "geometry": {"type": "Polygon", "coordinates": []},
                    "properties": {"state_code": "14", "district_code": "01"},
                }
            ],
        },
        level="federal_district",
        state_code="14",
        meta=DatasetMeta(filters={}),
        observations=[
            HistoryDTO(
                year=2024,
                level="federal_district",
                territory_code="01",
                district_plan="DERFE2023",
                ln=1000,
                sv=600,
                nv=400,
                ns=0,
                abstention_pct=40.0,
                coverage_share=0.96,
                eligible=True,
            )
        ],
    )
    body = json.loads(output)
    assert body["metadata"]["state_code"] == "14"
    props = body["features"][0]["properties"]
    assert props["observed_year"] == 2024
    assert props["observation_label"] == "Observado 2024"
    assert props["observed_abstention_pct"] == 40.0
    assert props["coverage_share"] == 0.96
    assert not any("2027" in key or "prediction" in key for key in props)


def test_district_fiche_is_observed_2024_and_has_coverage_not_forecast():
    from participa_geo.api.schemas.history import HistoryDTO

    report = generate_district_observed_fiche(
        HistoryDTO(
            year=2024,
            name="Distrito 01",
            level="federal_district",
            territory_code="01",
            district_plan="DERFE2023",
            ln=1000,
            sv=600,
            nv=400,
            ns=0,
            eligible=True,
            coverage_share=0.96,
        )
    )
    text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(report)).pages)
    assert "Observado 2024" in text
    assert "96.0%" in text
    assert "Predicción" not in text
    assert "2027" not in text


def test_real_national_pdfs_use_artifact_metrics_and_avoid_jalisco_only_claims():
    context = load_delivery_context()
    assert context.national is True
    assert context.cohort.total == 2477
    assert context.cohort.eligible == 1623
    assert context.cohort.insufficient == 854
    assert context.model.mae_2021 == pytest.approx(12.185402021052685)
    assert context.model.mae_2024 == pytest.approx(5.560229306808839)
    methodology = " ".join(
        page.extract_text() or ""
        for page in PdfReader(io.BytesIO(generate_methodology(context))).pages
    )
    executive = " ".join(
        page.extract_text() or ""
        for page in PdfReader(io.BytesIO(generate_executive(context))).pages
    )
    assert "2477" in methodology and "2477" in executive
    assert "Jalisco" not in methodology and "Jalisco" not in executive
