"""Report generation and download endpoints (T9).

Small exports (history, scenario CSV/GeoJSON/PDF/maps) are generated
synchronously and stored atomically. Institutional PDFs and the technical ZIP are
*only* served when the CLI ``deliver`` command has already published them; the
API never queues a job or reports a ``pending`` state.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import FileResponse

from participa_geo.api.deps import SessionDep
from participa_geo.api.errors import ProblemException, problem
from participa_geo.api.gis_client import AllowedLayer, GeoServerClient, GeoServerError
from participa_geo.api.metadata import build_meta
from participa_geo.api.schemas.common import Page
from participa_geo.api.schemas.history import HistoryDTO
from participa_geo.api.schemas.reports import (
    INSTITUTIONAL_KINDS,
    MEDIA_TYPE_BY_FORMAT,
    MODEL_KINDS,
    REPORT_RULES_VERSION,
    ReportArtifactDTO,
    ReportRequest,
)
from participa_geo.api.schemas.scenarios import ScenarioDTO
from participa_geo.db.repository import Repository
from participa_geo.reporting.delivery import repo_root
from participa_geo.reporting.geojson import GeoJSONExportError, export_scenario_geojson
from participa_geo.reporting.maps import MapRenderError, render_scenario_map
from participa_geo.reporting.national import (
    export_national_geojson,
    generate_district_observed_fiche,
    generate_observed_territory_fiche,
)
from participa_geo.reporting.pdf import generate_scenario_pdf
from participa_geo.reporting.store import (
    ExportLimitError,
    InstitutionalPackageNotGenerated,
    ReportQuotaError,
    ReportStore,
    ReportStoreError,
)
from participa_geo.reporting.tables import (
    export_history,
    export_model_evidence,
    export_scenario_csv,
)
from participa_geo.scenarios.service import ScenarioService

router = APIRouter()

GEOGRAPHIC_WARNING = (
    "Referencia cartográfica INE 2025-12-15. No implica igualdad de límites "
    "históricos (footprint_status=not_verified)."
)


class ReportValidationError(RuntimeError):
    """A request that passed Pydantic but cannot be represented as an export."""


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _resolve(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repo_root() / path


def _problem(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    **extensions: Any,
) -> ProblemException:
    return ProblemException(
        problem(
            status=status_code,
            code=code,
            title=title,
            detail=detail,
            instance=request.url.path,
            **extensions,
        )
    )


def _source_metadata() -> dict[str, Any]:
    """Read the provenance and model manifest for export metadata."""
    root = repo_root()
    processed = root / "data" / "processed"
    national = processed / "national"
    if (national / "model" / "manifest.json").is_file():
        processed = national
    sources: list[dict] = []
    provenance_name = "national-ingest.json" if processed == national else "provenance.json"
    provenance_path = processed / provenance_name
    if provenance_path.is_file():
        try:
            body = json.loads(provenance_path.read_text(encoding="utf-8"))
            if processed == national:
                sources = [
                    {
                        "year": item.get("year"),
                        "source_url": item.get("source_url"),
                        "member": item.get("zip"),
                        "sha256": item.get("zip_sha256"),
                        "municipality_count": body.get("municipality_count"),
                    }
                    for item in sorted(
                        body.get("sources", []), key=lambda row: int(row.get("year", 0))
                    )
                ]
            else:
                sources = [
                    {
                        "year": item.get("year"),
                        "source_url": item.get("source_url"),
                        "member": item.get("member"),
                        "sha256": item.get("sha256"),
                        "municipality_count": item.get("municipality_count"),
                    }
                    for item in sorted(
                        body.get("sources", []), key=lambda row: int(row.get("year", 0))
                    )
                ]
        except (OSError, ValueError, TypeError):
            sources = []
    model_meta: dict[str, Any] = {}
    manifest_path = processed / "model" / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            model_meta = {
                "family": manifest.get("family"),
                "model_run_id": manifest.get("model_run_id"),
                "data_aggregate_sha256": manifest.get("data_aggregate_sha256"),
                "reference_date": manifest.get("reference_date"),
                "versions": manifest.get("versions"),
            }
        except (OSError, ValueError, TypeError):
            model_meta = {}
    return {"sources": sources, "model": model_meta}


def _cache_key(
    body: ReportRequest,
    meta,
    *,
    scenario: ScenarioDTO | None = None,
) -> str:
    payload: dict[str, Any] = {
        "kind": body.kind,
        "level": body.level,
        "district_plan": body.district_plan,
        "state_code": body.state_code,
        "territory_id": str(body.territory_id) if body.territory_id else None,
        "year": body.year,
        "scenario_id": str(body.scenario_id) if body.scenario_id else None,
        "dataset_version_ids": sorted(str(item) for item in meta.dataset_version_ids),
        "model_run_id": str(meta.model_run_id) if meta.model_run_id else None,
        "reference_date": meta.reference_date,
        "filters": meta.filters,
        "report_rules_version": REPORT_RULES_VERSION,
        "geographic_warning": meta.geographic_warning,
    }
    if scenario is not None:
        payload.update(
            {
                "scenario_input_sha256": scenario.input_sha256,
                "scenario_model_sha256": scenario.model_sha256,
                "assumption_code": scenario.assumption_code,
                "assumption_version": scenario.assumption_version,
                "rules_version": scenario.rules_version,
                "requested_reduction_pp": scenario.requested_reduction_pp,
            }
        )
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _history_meta(repo: Repository, body: ReportRequest, *, kind: str):
    return build_meta(
        dataset_version_ids=repo.get_dataset_version_ids(),
        model_run_id=repo.get_published_model_run_id(),
        geographic_warning=GEOGRAPHIC_WARNING,
        filters={
            "report_kind": kind,
            "territory_id": str(body.territory_id) if body.territory_id else None,
            "year": body.year,
            "page": 1,
            "level": body.level,
            "district_plan": body.district_plan,
            "state_code": body.state_code,
            "page_size": 20_000,
        },
    )


def _history_rows(repo: Repository, body: ReportRequest) -> list[HistoryDTO]:
    records, total = repo.get_history(
        territory_id=body.territory_id,
        year=body.year,
        page=1,
        page_size=20_000,
        level=body.level,
        state_code=body.state_code,
    )
    if total > 20_000:
        raise ReportValidationError(
            "La exportación supera el límite nacional de 20,000 filas; aplique un filtro."
        )
    return [
        HistoryDTO(
            territory_id=record.territory_id,
            year=record.year,
            name=record.name,
            municipality_code=record.municipality_code,
            ln=record.ln,
            sv=record.sv,
            nv=record.nv,
            ns=record.ns,
            participation_pct=record.participation_pct,
            abstention_pct=record.abstention_pct,
            unknown_share=record.unknown_share,
            ns_lower_pct=record.ns_lower_pct,
            ns_upper_pct=record.ns_upper_pct,
            eligible=record.eligible,
            identity_status=record.identity_status,
            footprint_status=record.footprint_status,
            level=record.level,
            territory_code=record.territory_code,
            district_plan=record.district_plan,
            coverage_share=record.coverage_share,
        )
        for record in records
    ]


def _scenario(session, scenario_id: UUID | None) -> ScenarioDTO:
    if scenario_id is None:
        raise ReportValidationError("scenario_id es obligatorio para este tipo de reporte")
    scenario = ScenarioService(session).get(scenario_id)
    if scenario is None:
        raise LookupError(str(scenario_id))
    return scenario


def _scenario_meta(repo: Repository, scenario: ScenarioDTO, body: ReportRequest):
    return build_meta(
        dataset_version_ids=repo.get_dataset_version_ids(),
        model_run_id=scenario.model_run_id,
        geographic_warning=GEOGRAPHIC_WARNING,
        filters={
            "report_kind": body.kind,
            "scenario_id": str(scenario.scenario_id),
            "target_year": scenario.target_year,
        },
    )


def _filename(body: ReportRequest, scenario_id: UUID | None) -> str:
    if body.kind == "history_csv":
        return f"participa-geo-historial-{body.level}-{body.state_code}-{body.year or 'todos'}.csv"
    if body.kind == "history_xlsx":
        return f"participa-geo-historial-{body.level}-{body.state_code}-{body.year or 'todos'}.xlsx"
    if body.kind == "district_observed_pdf":
        return f"participa-geo-distrito-observado-2024-{body.territory_id}.pdf"
    if body.kind == "territory_fiche_pdf":
        return f"participa-geo-ficha-observada-2024-{body.territory_id or body.state_code}.pdf"
    if body.kind == "national_geojson":
        return f"participa-geo-{body.level}-{body.state_code}.geojson"
    suffix = {
        "scenario_csv": "csv",
        "scenario_geojson": "geojson",
        "scenario_pdf": "pdf",
        "scenario_map_png": "png",
        "scenario_map_pdf": "pdf",
    }[body.kind]
    return f"participa-geo-escenario-{scenario_id}.{suffix}"


def _store(request: Request) -> ReportStore:
    return request.app.state.report_store


@router.post(
    "/reports",
    response_model=ReportArtifactDTO,
    status_code=status.HTTP_201_CREATED,
    tags=["reports"],
)
def create_report(
    request: Request,
    body: ReportRequest,
    response: Response,
    *,
    session: SessionDep,
) -> ReportArtifactDTO:
    store = _store(request)
    repo = Repository(session)
    client = _client_key(request)
    sources = _source_metadata()

    try:
        if body.kind in INSTITUTIONAL_KINDS:
            artifact = store.get_or_create(
                body,
                builder=lambda: b"",
                filename=f"{body.kind}.pdf",
                media_type="application/pdf",
                sources=sources,
                cache_key=body.kind,
                client_key=client,
            )
            response.status_code = status.HTTP_200_OK
            return artifact

        if body.kind in MODEL_KINDS:
            model_run_id = repo.get_published_model_run_id()
            if model_run_id is None:
                raise _problem(
                    request,
                    status_code=409,
                    code="conflict",
                    title="Estado en conflicto",
                    detail="No se ha cargado ningún modelo.",
                )
            meta = build_meta(
                dataset_version_ids=repo.get_dataset_version_ids(),
                model_run_id=model_run_id,
                geographic_warning=GEOGRAPHIC_WARNING,
                filters={"report_kind": body.kind},
            )
            fmt = "csv" if body.kind.endswith("_csv") else "xlsx"

            def builder() -> bytes:
                national_model_dir = repo_root() / "data" / "processed" / "national" / "model"
                model_dir = (
                    national_model_dir
                    if (national_model_dir / "model.json").is_file()
                    else repo_root() / "data" / "processed" / "model"
                )
                return export_model_evidence(
                    fmt,
                    model_dir,
                    meta,
                    sources=sources,
                )

            media_type = MEDIA_TYPE_BY_FORMAT[fmt]
            artifact = store.get_or_create(
                body,
                builder=builder,
                filename=f"participa-geo-evidencia-modelo.{fmt}",
                media_type=media_type,
                sources=sources,
                cache_key=_cache_key(body, meta),
                client_key=client,
                model_run_id=model_run_id,
            )
            response.status_code = (
                status.HTTP_200_OK if artifact.cached else status.HTTP_201_CREATED
            )
            return artifact

        if body.kind == "national_geojson":
            meta = build_meta(
                dataset_version_ids=repo.get_dataset_version_ids(),
                model_run_id=repo.get_published_model_run_id(),
                geographic_warning=GEOGRAPHIC_WARNING,
                filters={
                    "report_kind": body.kind,
                    "level": body.level,
                    "district_plan": body.district_plan,
                    "state_code": body.state_code,
                },
            )
            layer = (
                AllowedLayer.districts_2023
                if body.level == "federal_district"
                else AllowedLayer.municipalities
            )
            client_gis = GeoServerClient(request.app.state.settings.gis_base_url)
            raw_geojson = client_gis.get_features(
                layer, None, None, count=1000, state_code=body.state_code
            )
            feature_collection = json.loads(raw_geojson)
            observations: list[HistoryDTO] = []
            if body.level == "federal_district":
                records, total = repo.get_history(
                    territory_id=None,
                    year=2024,
                    page=1,
                    page_size=1000,
                    level="federal_district",
                    state_code=body.state_code,
                )
                if total > 1000:
                    raise ReportValidationError("la exportación distrital excede 1,000 geometrías")
                observations = [
                    HistoryDTO(
                        territory_id=row.territory_id,
                        year=row.year,
                        name=row.name,
                        municipality_code=row.municipality_code,
                        level=row.level,
                        territory_code=row.territory_code,
                        district_plan=row.district_plan,
                        ln=row.ln,
                        sv=row.sv,
                        nv=row.nv,
                        ns=row.ns,
                        participation_pct=row.participation_pct,
                        abstention_pct=row.abstention_pct,
                        unknown_share=row.unknown_share,
                        ns_lower_pct=row.ns_lower_pct,
                        ns_upper_pct=row.ns_upper_pct,
                        eligible=row.eligible,
                        coverage_share=row.coverage_share,
                    )
                    for row in records
                ]

            def builder() -> bytes:
                return export_national_geojson(
                    feature_collection,
                    level=body.level,
                    state_code=body.state_code,
                    meta=meta,
                    observations=observations,
                    sources=sources,
                )

            artifact = store.get_or_create(
                body,
                builder=builder,
                filename=_filename(body, None),
                media_type=MEDIA_TYPE_BY_FORMAT["geojson"],
                sources=sources,
                cache_key=_cache_key(body, meta),
                client_key=client,
                model_run_id=meta.model_run_id,
            )
            response.status_code = (
                status.HTTP_200_OK if artifact.cached else status.HTTP_201_CREATED
            )
            return artifact

        if body.kind in {"district_observed_pdf", "territory_fiche_pdf"}:
            meta = build_meta(
                dataset_version_ids=repo.get_dataset_version_ids(),
                geographic_warning=GEOGRAPHIC_WARNING,
                filters={
                    "report_kind": body.kind,
                    "level": body.level,
                    "district_plan": body.district_plan,
                    "territory_id": str(body.territory_id) if body.territory_id else None,
                    "observed_year": 2024,
                },
            )
            rows = _history_rows(repo, body.model_copy(update={"year": 2024}))
            if len(rows) != 1:
                raise LookupError(str(body.territory_id))
            observed = rows[0]
            fiche_builder = (
                generate_district_observed_fiche
                if body.kind == "district_observed_pdf"
                else generate_observed_territory_fiche
            )
            artifact = store.get_or_create(
                body,
                builder=lambda: fiche_builder(observed),
                filename=_filename(body, None),
                media_type=MEDIA_TYPE_BY_FORMAT["pdf"],
                sources=sources,
                cache_key=_cache_key(body, meta),
                client_key=client,
            )
            response.status_code = (
                status.HTTP_200_OK if artifact.cached else status.HTTP_201_CREATED
            )
            return artifact

        scenario: ScenarioDTO | None = None
        if body.kind.startswith("scenario_"):
            scenario = _scenario(session, body.scenario_id)

        if body.kind in {"history_csv", "history_xlsx"}:
            meta = _history_meta(repo, body, kind=body.kind)
            rows = _history_rows(repo, body)
            fmt = "csv" if body.kind == "history_csv" else "xlsx"

            def builder() -> bytes:
                return export_history(rows, fmt, meta, sources=sources)

            media_type = MEDIA_TYPE_BY_FORMAT[fmt]
        else:
            assert scenario is not None
            meta = _scenario_meta(repo, scenario, body)
            if body.kind == "scenario_csv":

                def builder() -> bytes:
                    return export_scenario_csv(scenario, meta, sources=sources)

                media_type = MEDIA_TYPE_BY_FORMAT["csv"]
            elif body.kind == "scenario_geojson":
                reference = _resolve(request.app.state.settings.reference_geojson_path)

                def builder() -> bytes:
                    return export_scenario_geojson(scenario, reference, meta, sources=sources)

                media_type = MEDIA_TYPE_BY_FORMAT["geojson"]
            elif body.kind == "scenario_pdf":

                def builder() -> bytes:
                    return generate_scenario_pdf(scenario, meta)

                media_type = MEDIA_TYPE_BY_FORMAT["pdf"]
            elif body.kind in {"scenario_map_png", "scenario_map_pdf"}:
                fmt = "png" if body.kind == "scenario_map_png" else "pdf"

                def builder() -> bytes:
                    return render_scenario_map(scenario, fmt)

                media_type = MEDIA_TYPE_BY_FORMAT[fmt]
            else:  # pragma: no cover - closed Pydantic enum
                raise ReportValidationError("tipo de reporte no implementado")

        artifact = store.get_or_create(
            body,
            builder=builder,
            filename=_filename(body, scenario.scenario_id if scenario else None),
            media_type=media_type,
            sources=sources,
            cache_key=_cache_key(body, meta, scenario=scenario),
            client_key=client,
            model_run_id=meta.model_run_id,
            scenario_id=scenario.scenario_id if scenario else None,
        )
    except ExportLimitError as exc:
        detail = (
            "Ya hay una exportación en curso para este cliente."
            if exc.active
            else "Se alcanzó el límite de 10 exportaciones nuevas por minuto."
        )
        raise _problem(
            request,
            status_code=429,
            code="rate_limited",
            title="Demasiadas solicitudes",
            detail=detail,
            retry_after_seconds=exc.retry_after_seconds,
        ) from None
    except ReportQuotaError as exc:
        raise _problem(
            request,
            status_code=503,
            code="quota_exceeded",
            title="Capacidad de exportaciones agotada",
            detail=str(exc),
        ) from None
    except InstitutionalPackageNotGenerated:
        raise _problem(
            request,
            status_code=409,
            code="institutional_package_not_generated",
            title="Paquete institucional no generado",
            detail=(
                "El documento institucional sólo se sirve después de generarlo con "
                "`participa_geo.cli deliver`. No hay cola ni estado pendiente."
            ),
        ) from None
    except MapRenderError as exc:
        raise _problem(
            request,
            status_code=503,
            code="unavailable",
            title="Servicio no disponible",
            detail=f"No se pudo generar el mapa real: {exc}",
        ) from None
    except GeoServerError as exc:
        raise _problem(
            request,
            status_code=503,
            code="unavailable",
            title="Servicio no disponible",
            detail=f"No se pudo obtener GeoJSON nacional: {exc}",
        ) from None
    except LookupError:
        raise _problem(
            request,
            status_code=404,
            code="not_found",
            title="Recurso no encontrado",
            detail="El escenario solicitado no existe.",
        ) from None
    except ReportValidationError as exc:
        raise _problem(
            request,
            status_code=422,
            code="validation_error",
            title="Validación fallida",
            detail=str(exc),
        ) from None
    except (GeoJSONExportError, ReportStoreError) as exc:
        raise _problem(
            request,
            status_code=503,
            code="unavailable",
            title="Servicio no disponible",
            detail=f"No se pudo generar el archivo: {exc}",
        ) from None

    response.status_code = status.HTTP_200_OK if artifact.cached else status.HTTP_201_CREATED
    return artifact


@router.get("/reports", response_model=Page[ReportArtifactDTO], tags=["reports"])
def list_reports(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[ReportArtifactDTO]:
    store = _store(request)
    items = store.list(limit=1000)
    start = (page - 1) * page_size
    window = items[start : start + page_size]
    return Page(
        items=window,
        page=page,
        page_size=page_size,
        total=len(items),
        meta=build_meta(geographic_warning=GEOGRAPHIC_WARNING),
    )


@router.get("/reports/{report_id}", response_model=ReportArtifactDTO, tags=["reports"])
def get_report(request: Request, report_id: UUID) -> ReportArtifactDTO:
    artifact = _store(request).get(report_id)
    if artifact is None:
        raise _problem(
            request,
            status_code=404,
            code="not_found",
            title="Recurso no encontrado",
            detail="El reporte solicitado no existe.",
        )
    return artifact


@router.get("/reports/{report_id}/download", tags=["reports"])
def download_report(request: Request, report_id: UUID) -> FileResponse:
    store = _store(request)
    artifact = store.get(report_id)
    if artifact is None:
        raise _problem(
            request,
            status_code=404,
            code="not_found",
            title="Recurso no encontrado",
            detail="El reporte solicitado no existe.",
        )
    if artifact.status != "ready":
        raise _problem(
            request,
            status_code=409,
            code="conflict",
            title="Estado en conflicto",
            detail="El reporte no está disponible para descarga.",
        )
    path = store.path_for(report_id)
    if path is None:
        raise _problem(
            request,
            status_code=409,
            code="conflict",
            title="Estado en conflicto",
            detail="El archivo generado ya no está disponible.",
        )
    media_type = MEDIA_TYPE_BY_FORMAT[artifact.format]
    return FileResponse(
        path,
        media_type=media_type,
        filename=artifact.filename or path.name,
        headers={"Cache-Control": "private, max-age=0, must-revalidate"},
    )


__all__ = ["GEOGRAPHIC_WARNING", "ReportValidationError", "router"]
