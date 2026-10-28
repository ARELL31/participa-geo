from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from participa_geo.api.schemas.common import DatasetMeta
from participa_geo.api.schemas.history import HistoryDTO
from participa_geo.api.schemas.reports import ReportRequest
from participa_geo.cli import build_parser
from participa_geo.reporting.delivery import (
    _sources_json,
    _sources_markdown,
    context_manifest,
    load_delivery_context,
)
from participa_geo.reporting.national import (
    export_national_geojson,
    generate_district_observed_fiche,
    generate_observed_territory_fiche,
)
from participa_geo.reporting.pdf import generate_executive, generate_methodology
from participa_geo.reporting.tables import ModelEvidenceLimitError, export_model_evidence


def test_delivery_confirmation_help_names_authorized_continuity_sources(capsys):
    with pytest.raises(SystemExit) as result:
        build_parser().parse_args(["deliver", "--help"])

    assert result.value.code == 0
    help_text = capsys.readouterr().out
    assert "ACCDB" in help_text
    assert "histórico seccional" in help_text
    assert "catálogo de cabeceras" in help_text


def test_report_request_carries_level_and_plan_metadata():
    request = ReportRequest(
        kind="history_csv", level="federal_district", district_plan="DERFE2023", year=2024
    )
    assert request.level == "federal_district"
    assert request.district_plan == "DERFE2023"


def test_state_fiche_uses_state_name_and_entidad_label():
    record = HistoryDTO(
        territory_id=None,
        year=2024,
        name="JALISCO",
        level="municipality",
        ln=100,
        sv=60,
        nv=40,
        ns=0,
        eligible=False,
    )
    text = " ".join(page.extract_text() or "" for page in PdfReader(
        io.BytesIO(generate_observed_territory_fiche(record))
    ).pages)
    assert "Ficha entidad" in text
    assert "Entidad" in text
    assert "JALISCO" in text
    assert "Distrito" not in text


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


def test_national_model_evidence_is_bounded_and_state_identified():
    model_dir = Path("data/processed/national/model")
    exported = export_model_evidence("csv", model_dir, DatasetMeta(filters={}))
    text = exported.decode("utf-8-sig")
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    reader = csv.DictReader(lines)
    rows = list(reader)

    assert "state_code" in reader.fieldnames
    assert "state_name" in reader.fieldnames
    assert len(rows) <= 20_000
    assert {"feature", "exclusion", "contribution_selected"}.issubset(
        {row["record_type"] for row in rows}
    )
    assert "contribution_candidate_m1" not in {row["record_type"] for row in rows}
    assert all(row["state_code"] and row["state_name"] for row in rows)
    assert any("candidate_m1_detail_omitted" in line for line in text.splitlines())


def test_model_evidence_over_limit_fails_without_truncating(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.json").write_text(
        json.dumps(
            {
                "level": "municipality",
                "model_run_id": "run",
                "features_2027": [
                    {"municipality_code": f"{index:05}", "features": {"ln": index}}
                    for index in range(20_001)
                ],
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "evaluation.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ModelEvidenceLimitError, match="no se generó una exportación truncada"):
        export_model_evidence("csv", model_dir, DatasetMeta(filters={}))


def test_delivery_attribution_includes_all_mgs_sources_and_checksums():
    context = load_delivery_context()
    source_doc = json.loads(_sources_json(context, include_raw_sources=False))
    sources_markdown = _sources_markdown(context, include_raw_sources=True).decode()

    continuity_sources = source_doc["continuity_sources"]
    expected_checksums = {
        "data/raw/continuity/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb": (
            "f88804f66fa0bcfc855159a1c2332be06f283bd697e2a037e8a70db3fc5934aa"
        ),
        "data/raw/continuity/official-section-history.csv": (
            "e91f0f6199a8efeaf755fcc9a4c08e705bc15508d060398b627876582af6f5cb"
        ),
        "data/raw/continuity/district-headquarters.txt": (
            "c244b4ed3e55c668a4a8fde4a8f5999fa95d8974b6a45a5ef91660a5c1a4fb47"
        ),
    }
    assert {item["member"]: item["sha256"] for item in continuity_sources} == expected_checksums
    assert all(item["source_url"] for item in continuity_sources)
    assert all(item["member"] in sources_markdown for item in continuity_sources)
    assert all(item["sha256"] in sources_markdown for item in continuity_sources)
    csv_source = next(
        item
        for item in continuity_sources
        if item["member"].endswith("official-section-history.csv")
    )
    assert csv_source["derived_from"].endswith(".accdb")
    assert csv_source["derived_using"] == "scripts/export_official_section_history.sh"
    assert "se incluyen los originales de fuentes con atribución" in sources_markdown

    geography_sources = source_doc["geography_sources"]
    assert len(geography_sources) == 32
    assert len({item["state_code"] for item in geography_sources}) == 32
    assert all(
        item["source_url"].endswith(f"/{item['state_code']}.zip")
        for item in geography_sources
    )
    assert all(len(item["sha256"]) == 64 and item["attribution"] for item in geography_sources)
    assert sum(item["source_url"] in sources_markdown for item in geography_sources) == 32
    assert sources_markdown.count("`" + "0" * 64 + "`") == 0
    assert "15-DIC-2025" in sources_markdown
    manifest = context_manifest(context)
    assert len(manifest["geography_sources"]) == 32
    assert source_doc["sources"] and len(source_doc["sources"]) == 6

    report_text = " ".join(
        page.extract_text() or ""
        for page in PdfReader(io.BytesIO(generate_methodology(context))).pages
    )
    report_text_compact = "".join(report_text.split())
    for item in geography_sources:
        assert item["source_url"] in report_text
        assert item["sha256"] in report_text_compact


def test_delivery_attribution_does_not_require_raw_mgs_archives(monkeypatch):
    original_is_file = Path.is_file

    def is_file(path: Path) -> bool:
        if "data/raw/gis/national" in path.as_posix():
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", is_file)
    context = load_delivery_context()
    assert len(context.geography_sources) == 32
    assert all(len(source.sha256) == 64 for source in context.geography_sources)
