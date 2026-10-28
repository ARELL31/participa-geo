# PARTICIPA-GEO Nacional Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Extender el MVP verificado de Jalisco a una plataforma nacional con municipios y distritos federales seleccionables, datos 2009–2024, dos modelos separados, GIS nacional y entregables reproducibles.

**Architecture:** Monorepositorio FastAPI/React. El CCPC se almacena en grano de sección y se agrega a municipio y distrito; el distrito usa el plan 2023 reconstruido por sección, con compuerta de cobertura. Los modelos municipal y distrital se entrenan y validan por separado; el distrito nunca se obtiene promediando municipios. GeoServer publica WMS nacional y WFS por entidad/bbox.

**Tech Stack:** Python 3.12, FastAPI/Pydantic2, SQLAlchemy2/Alembic/psycopg3, pandas/NumPy/scikit-learn, PostgreSQL/PostGIS, GeoServer; React/TypeScript/Vite/MapLibre/TanStack Query/Radix/Lucide; pytest/Vitest/Playwright; Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-27-participa-geo-national-design.md` — aprobada por el usuario.

**Estado de ejecución:** plan aprobado el 2026-10-27; método: agentes con ChatGPT Luna; respaldo Gemini 3.8 Flash si se agotan los tokens. Implementación autorizada.

## Global Constraints

- Cobertura: 32 entidades, 2,477 municipios, 300 distritos federales; seis CCPC 2009/2012/2015/2018/2021/2024; objetivo 2027 federal intermedio.
- Dos niveles: `municipality` y `federal_district`; el usuario elige. Nunca sumar predicciones municipales para producir un distrito.
- CCPC nativo: 54,872,712 filas, 3.73 GB descomprimidos; `LN=SV+NV+NS` al 100%; parser CSV formal; códigos INE normalizados; Oaxaca contiene nombres entrecomillados.
- Distritos: `DERFE2021` para 2009–2021 y `DERFE2023` para 2024. Se publica el plan **2023**; la historia 2009–2021 se reconstruye por sección y se etiqueta, no se presenta como oficial.
- Continuidad seccional validada; no unir números de sección a ciegas. `unmatched` no se imputa. Cobertura mínima: **98% nacional** y **95% por distrito** sobre LN2024 de referencia.
- Plan distrital 2023; 2021 queda en auditoría. Los 7 números nuevos son elegibles sólo si sus secciones tienen continuidad suficiente.
- Municipio–distrito es N:M: 2,581 pares, 72 municipios partidos (MGS), hasta 5 distritos. No asignación 1:1 ni distrito dominante.
- API v1: `state_code` default `"14"` para compatibilidad; nacional explícito `state_code=all`. `page_size<=500`; escenarios máximo 1,000 municipios/300 distritos; JSON 128 KiB.
- WMS nacional; WFS sólo por entidad/bbox, máximo 1,000 features; no descargar 2,477 geometrías completas.
- Modelos: M0 mismo tipo t-6; M1 StandardScaler+Ridge(alpha=1.0), seis features + efectos fijos de entidad. Selección por MAE2021; empate M0; test2024 congelado.
- Calidad `SV+NV>=1000`, `NS/LN<=0.10`; cohortes separadas; insuficiente nunca cero; banda P90 de errores2021, mínimo30, cobertura empírica2024.
- `model_run_id` incluye nivel, plan, datos, identidad, cohortes/exclusiones, M0/M1 y métricas. Cambiar evidencia cambia ID.
- Reportes: PDF nacional/metodológico y fichas; CSV/XLSX hasta20,000 filas; GeoJSON por entidad/nivel; ZIP técnico con fuentes sólo con confirmación de licencia; sin cartas/secretos/PII.
- Diseño visual: paleta guinda/blanco del MVP, Inter local, Lucide, estados textuales, foco visible, 320/375/1440; no AA certificado.
- TDD, commits pequeños, verificación real. Docker vía `sg docker -c`; sin sudo, instalaciones host, socket Docker, ni cambios de firewall/SELinux.

## Review Focus

1. **Distrito mal etiquetado como municipio o plan equivocado:** una ficha distrital no debe mostrar tasas municipales ni usar 2021 como 2023. Pruebas en N3/N6/N9.
2. **Cobertura distrital silenciosa:** secciones sin continuidad o sin geometría no deben producir una tasa completa. Pruebas en N3/N6/N10.
3. **Escala nacional:** 54.9M filas, 2,477 unidades, 300 distritos; una consulta o WFS no debe cargar el país completo ni agotar memoria. Pruebas en N2/N4/N7/N11.
4. **Mezcla de niveles/planes:** un escenario no puede combinar municipios y distritos, ni planes 2021/2023. Pruebas en N7/N9.
5. **Datos faltantes y nuevas claves:** 2009/2012 sin `DEF`, municipios ausentes, 19 altas y distritos nuevos no deben heredar historia ni convertirse en cero. Pruebas en N2/N3/N6.

---

## File Structure

| Zona | Archivos y responsabilidad |
|---|---|
| Dominio | `apps/api/participa_geo/territory.py` (niveles, claves, UUIDs, planes) |
| Persistencia | `apps/api/participa_geo/db/models.py`, `alembic/versions/0004_national_levels.py`, `0005_section_fact.py`, `0006_continuity.py` |
| Ingestión | `ingestion/national.py`, `ingestion/section_fact.py`, `ingestion/continuity.py`; `pipelines/ingestion/national.py`; `pipelines/validation/continuity.py`; CLI |
| GIS | `pipelines/validation/geography_national.py`, `gis/geoserver/national.py`, `gis/styles/national_*.sld` |
| Modelos | `prediction/national.py`, `prediction/district.py`, `prediction/artifacts.py`, `pipelines/training/national.py` |
| API | `api/schemas/{territory,national,scenarios}.py`, `api/routes/{summary,national_predictions,district_scenarios}.py`, `api/gis_client.py` |
| Frontend | `apps/web/src/app/filters.ts`, `components/LevelSwitcher.tsx`, `features/national/*`, `features/territory/*`, `features/prediction/*`, `features/scenarios/*` |
| Reportes | `reporting/national.py`, `reporting/delivery.py`, `infrastructure/scripts/verify_delivery.py` |
| Pruebas | `tests/unit/national/`, `tests/integration/national/`, `tests/contract/national/`, `tests/e2e/national/` |

No crear carpetas vacías ni servicios nuevos. Extender los módulos existentes cuando la responsabilidad sea la misma.

## Contratos de dominio

Definir en `territory.py` y reutilizar:

```python
TerritoryLevel = Literal["municipality", "federal_district"]
DistrictPlan = Literal["DERFE2021", "DERFE2023"]

@dataclass(frozen=True)
class TerritoryKey:
    level: TerritoryLevel
    state_code: str
    code: str
    district_plan: DistrictPlan | None = None

def territory_id(key: TerritoryKey) -> UUID: ...
def observation_id(key: TerritoryKey, year: int, source_version_id: UUID) -> UUID: ...
```

- Municipio: `code` es la clave municipal de 3 dígitos; `district_plan=None`.
- Distrito: `code` es el número federal de 2 dígitos; `district_plan` obligatorio.
- `territory_id` distingue nivel y plan. `observation_id` incluye dataset y plan.
- `SectionFact`: `year,state_code,municipality_code,section,district_2021,district_2023,sex,age,ln,sv,nv,ns,dataset_version_id`.
- `AggregateObservation`: `TerritoryKey`, `year`, `ln,sv,nv,ns`, shares, quality, source.
- `Coverage`: `TerritoryKey`, `year`, `matched_ln`, `reference_ln`, `coverage`, `status`.
- `NationalModelBundle`: `level`, `district_plan`, `model_run_id`, features, M0/M1, metrics, exclusions, predictions.
- `ScenarioRequest` añade `level: TerritoryLevel | None`; si se envía debe coincidir con el modelo. IDs de un solo nivel/plan.
- `TerritoryDTO` añade `level`, `territory_code`, `district_plan`; conserva `municipality_code` nullable por compatibilidad.

---

## Task N1: Dominio, esquema y migración de niveles

**Files:** `territory.py`; `db/models.py`; `alembic/versions/0004_national_levels.py`; `api/schemas/{common,territories,history,models}.py`; `tests/unit/national/test_territory.py`; `tests/integration/national/test_migration_levels.py`.

**Interfaces:**
- Consumes: MVP models, IDs y Alembic.
- Produces: `TerritoryKey`, `territory_id`, `observation_id`, columns `level`, `territory_code`, `district_plan`, `valid_from/to`; DTOs with level.

- [ ] **Step 1 — Tests rojos:** `test_territory_id_differs_by_level` (municipio 14/001 ≠ distrito14/01/2023), `test_district_requires_plan`, `test_observation_id_includes_dataset_and_plan`, `test_legacy_jalisco_ids_preserved`, `test_mixed_level_scenario_rejected`.
- [ ] **Step 2 — RED:** `python -m pytest tests/unit/national/test_territory.py -q`; falla por símbolos/columnas ausentes.
- [ ] **Step 3 — Implementar:** tipos/UUIDs; migración 0004 con `level`, `territory_code`, `district_plan`, `valid_from/to`; backfill Jalisco como `municipality`; índices por `(level,state_code,territory_code,district_plan)`; DTOs aditivos.
- [ ] **Step 4 — GREEN:** migrar una base limpia y ejecutar tests unitarios/contract; una fila Jalisco conserva su UUID e historia.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: add national territory levels and plan-aware identities'`.

## Task N2: Ingestión nacional de sección y agregado municipal

**Files:** `ingestion/national.py`, `ingestion/section_fact.py`; `pipelines/ingestion/national.py`; `cli.py`; `alembic/versions/0005_section_fact.py`; `data/sources.json`; `docs/methodology/national-ingestion.md`; tests.

**Interfaces:**
- Consumes: seis ZIP, `SourceManifest`, parser CSV, `SectionFact`.
- Produces: `read_national_ccpc(archive:Path, year:int)->Iterator[SectionFact]`; `ingest_national(source_dir:Path, output_dir:Path)->NationalIngestReport`; CLI `ingest-national`; `fact_ccpc_section` particionada por año; agregados municipales.
- Reporte: 54,872,712 filas, 32×6 CSV, 2,477 municipios, 0 descuadres.

- [ ] **Step 1 — Tests rojos:** parser de Oaxaca con coma entrecomillada; `EDOCVE=1`→`01`, `MPIOCVE=1`→`001`; `DEF` vacío 2009 no se imputa; `LN!=SV+NV+NS` falla; duplicado falla; fila municipal agregada por suma.
- [ ] **Step 2 — RED:** pytest enfocado; falla por módulos/tabla.
- [ ] **Step 3 — Implementar:** descarga/verificación SHA; parser streaming; COPY/particiones; agregado municipal; manifiesto `national-ingest.json`; CLI. No cargar 3.7 GB en RAM.
- [ ] **Step 4 — GREEN y datos reales:** ingestión completa; comparar con `national-audit` (54,872,712 filas, 2,477 municipios, 300 distritos, 0 descuadres, 44,154 `DEF` vacíos); repetir hash/idempotencia.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: ingest national CCPC section facts and municipal aggregates'`.

## Task N3: Continuidad seccional y reconstrucción distrital 2023

**Files:** `ingestion/continuity.py`; `pipelines/validation/continuity.py`; `alembic/versions/0006_continuity.py`; `cli.py`; `docs/methodology/national-district-reconstruction.md`; tests.

**Interfaces:**
- Consumes: `SectionFact`, MGS `SECCION`, catálogo histórico/ACCDB si disponible.
- Produces: `SectionContinuity` (source_year, section, target_section, evidence); `build_continuity(...)->ContinuityReport`; `reconstruct_district_2023(facts, continuity)->list[DistrictObservation]`; `district_coverage(...)->list[Coverage]`; `agg_municipality_district_year`.
- CLI: `continuity build`, `district rebuild`.
- Gate: 98% LN2024 nacional, 95% por distrito.

- [ ] **Step 1 — Tests rojos:** 2024 section→2023 district exact; unmatched not imputed; 2021 section reassignment; coverage denominator LN2024; district with <95% `insufficient`; 7 new numbers eligible only with continuity; 72 split municipalities; 2021 plan not mixed.
- [ ] **Step 2 — RED:** focused pytest; fail because continuity absent.
- [ ] **Step 3 — Implementar:** tabla de continuidad con evidencia; leer ACCDB/catálogo sólo con herramienta aprobada; si no hay fuente, `BLOCKED` y no publicar distrito; reconstrucción; coverage; `agg_municipality_district_year`.
- [ ] **Step 4 — GREEN:** 2024 exact; 2021/2018 coverage report; gate; national 98/95; store audit CSV/JSON.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: reconstruct 2023 federal districts with coverage gates'`.

**Nota de bloqueo:** si no se obtiene continuidad seccional defendible, N3 termina BLOCKED y N6/N9 no se implementan. No se sustituye por un join de números.

## Task N4: Cartografía nacional y GeoServer

**Files:** `pipelines/validation/geography_national.py`; `gis/geoserver/national.py`; `gis/styles/national_*.sld`; `cli.py`; tests; docs.

**Interfaces:**
- Consumes: 32 MGS ZIPs; `TerritoryKey`; `SectionContinuity`.
- Produces: `import_national_cartography(archive_dir:Path)->GeographyAudit`; `publish_national_layers(settings)->PublicationAudit`; capas `states`, `municipalities`, `districts_2023`; WMS/WFS; nombres de distrito desde cabeceras.
- CLI: `gis import-national`, `gis publish-national`, `gis verify-national`.

- [ ] **Step 1 — Tests rojos:** 32 ZIPs; 2,477 municipios; 300 distritos; UTM11–16→4326; state boundaries; district labels; WMS GetMap national; WFS state/bbox≤1,000; WFS-T rejected; no admin.
- [ ] **Step 2 — RED:** integration tests; fail because layers/tables absent.
- [ ] **Step 3 — Implementar:** transformación real; validación; simplificación; publicación; estilos; gateway state/bbox; no full-country WFS.
- [ ] **Step 4 — GREEN:** 32/32; 2,477/300; GetMap PNG; WFS 125 features for a state; Transaction rejected.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: publish national municipal and district cartography'`.

## Task N5: Modelo municipal nacional

**Files:** `prediction/national.py`; `prediction/artifacts.py`; `pipelines/training/national.py`; `cli.py`; docs/methodology/national-model.md; tests.

**Interfaces:**
- Consumes: `AggregateObservation` municipal; identities; quality.
- Produces: `build_national_cohort(...)`; `train_national(level='municipality', output_dir)->NationalModelBundle`; M0/M1; artifacts; `predictions-2027.parquet`; `evaluation.json`; `exclusions-by-cut.csv`.
- Features: seis + state fixed effects; selection2021; test2024; band2021; coverage2024.

- [ ] **Step 1 — Tests rojos:** no leakage; common cohort; scaler training-only; 2024 frozen; state effects; 2,477 rows incl. insufficient; model ID changes with identity/cohort/candidate; band coverage.
- [ ] **Step 2 — RED:** focused; fail.
- [ ] **Step 3 — Implementar:** cohort national; Ridge/Stats; metrics by state/level; artifacts; no cross-level.
- [ ] **Step 4 — GREEN:** full national train; coverage; M0/M1; insuff; goldens.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: train and evaluate the national municipal model'`.

## Task N6: Modelo distrital 2023

**Files:** `prediction/district.py`; `prediction/artifacts.py`; `pipelines/training/district.py`; `cli.py`; docs; tests.

**Interfaces:**
- Consumes: `DistrictObservation` reconstructed; `Coverage`; identities.
- Produces: `build_district_cohort(...)`; `train_district(...)`; 300 rows; M0/M1; insufficient; band; plan id; no municipal sum.
- Gate N3 must pass; else `DistrictModelUnavailable`.

- [ ] **Step 1 — Tests rojos:** coverage gate; 300 rows; new districts; no cross-plan; no municipal sum; band; model ID.
- [ ] **Step 2 — RED:** focused.
- [ ] **Step 3 — Implementar:** cohort; model; coverage; artifacts; `insufficient` for unmatched/new.
- [ ] **Step 4 — GREEN:** national district train; report coverage; expected insufficient count; no cross-level.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: train the 2023 federal district model with coverage gating'`.

## Task N7: API nacional por nivel y gateway GIS

**Files:** `api/schemas/{territories,history,national,scenarios}.py`; `api/routes/{territories,history,summary,predictions,scenarios,recommendations,gis}.py`; `api/gis_client.py`; `db/repository.py`; `docs/api/contracts.md`; OpenAPI; tests.

**Interfaces:**
- Consumes: aggregates/models N2–N6; `TerritoryKey`.
- Produces: `level`, `state_code=all`, `/participation/summary`, national predictions/models; scenario level/plan; GIS gateway; page_size500; 128KiB; OpenAPI TS.
- `/summary`: section-summed state counts + level-specific high/insufficient/coverage; map color observed abstention.

- [ ] **Step 1 — Tests rojos:** level filter; state14 legacy; all; summary counts; mixed level rejected; plan mismatch rejected; WFS state/bbox; max1,000; no CQL; insufficient null; page500.
- [ ] **Step 2 — RED:** contract/integration.
- [ ] **Step 3 — Implementar:** schemas/routes/repository; current clients still work; `state_code=all`; scenario limits; GIS filters.
- [ ] **Step 4 — GREEN:** contract/OpenAPI; 2,477/300; API values match aggregates; state summary sums.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: serve national municipal and district analytics by level'`.

## Task N8: Shell nacional y perfil municipal

**Files:** `apps/web/src/app/filters.ts`, `components/LevelSwitcher.tsx`, `features/national/*`, `features/territory/*`, `features/executive/*`, `lib/api.ts`, tests.

**Interfaces:**
- Consumes: API N7.
- Produces: `level` and `state` URL filters; national panel 32 states; level switcher; municipal profile; map WMS; summary; existing Jalisco tests adapted.
- `GlobalFilters={level,stateCode,territoryId,historicalYear}`; default level municipality, state all for national UI; historical year2024.

- [ ] **Step 1 — Tests rojos:** URL level/state; invalid level; state all; national summary; municipal profile; no 2,477 WFS; switch preserves year; insuff not zero; keyboard.
- [ ] **Step 2 — RED:** Vitest.
- [ ] **Step 3 — Implementar:** level switcher, state search, national panel, state choropleth, municipal page, WMS state; no full-country features.
- [ ] **Step 4 — GREEN:** Vitest/typecheck/build; Playwright national/municipal.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: add national level selector and municipal intelligence views'`.

## Task N9: Perfil distrital y relación municipio–distrito

**Files:** `apps/web/src/features/district/*`, `features/territory/MunicipalityDistrictPanel.tsx`, `features/scenarios/*`, tests.

**Interfaces:**
- Consumes: `/territories?level=federal_district`, `/participation/summary`, `/agg_municipality_district`, predictions.
- Produces: district profile with plan2023 badge; reconstructed history notice; constituent municipalities; municipal profile lists districts; no 1:1 label; district scenario only with district model.

- [ ] **Step 1 — Tests rojos:** district label contains `marco 2023`; reconstructed notice; municipal profile shows 2–5 districts; no “Distrito dominante”; district insuff not green; mixed scenario rejected; keyboard/mobile.
- [ ] **Step 2 — RED:** Vitest.
- [ ] **Step 3 — Implementar:** district page, intersection panel, plan note, map, scenario link.
- [ ] **Step 4 — GREEN:** Vitest/Playwright; 72 split cases; coverage.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: add federal district profiles and many-to-many municipal context'`.

## Task N10: Reportes y exportaciones nacionales

**Files:** `reporting/national.py`, `reporting/delivery.py`, `api/routes/reports.py`, `apps/web/src/features/reports/*`, `docs/hackathon/*`, scripts; tests.

**Interfaces:**
- Consumes: aggregates/models N2–N9.
- Produces: national methodology/executive PDFs; state/district/municipality fiches; CSV/XLSX up to20,000; GeoJSON by state/level; technical ZIP with national sources; manifest.
- No 2,477-row PDF; no raw data without license flag.

- [ ] **Step 1 — Tests rojos:** page counts; national counts; level/plan metadata; 20,000 limit; GeoJSON state; ZIP sources; no private; scenario CSV; formula escaping.
- [ ] **Step 2 — RED:** unit/integration.
- [ ] **Step 3 — Implementar:** reports; exports; UI actions; ZIP; verify.
- [ ] **Step 4 — GREEN:** PDFs, ZIP complete; real data.
- [ ] **Step 5 — Commit:** `git commit -m 'feat: generate national reports and reproducible exports'`.

## Task N11: Rendimiento, CI, cleanroom y aceptación

**Files:** `.github/workflows/ci.yml`, `tests/e2e/national/*`, `docs/architecture/deployment.md`, `docs/hackathon/verification-results.md`, `README.md`; tests.

**Interfaces:**
- Consumes: all N1–N10.
- Produces: perf tests WMS≤5s/WFS≤3s/API≤500ms; national E2E; cleanroom from ZIP; final acceptance.

- [ ] **Step 1 — Tests rojos:** WMS/WFS latency; API500; national E2E; state/district switch; cleanroom; no 2,477 WFS.
- [ ] **Step 2 — RED:** run and record.
- [ ] **Step 3 — Implementar:** caching/indexes/simplification/CI/scripts; fix root causes.
- [ ] **Step 4 — GREEN:** full suite, E2E, cleanroom, ZIP.
- [ ] **Step 5 — Commit:** `git commit -m 'test: verify national coverage, performance and clean-room delivery'`.

## Dependencies and parallelism

- N1→N2→N3→N4→N7→N8→N9→N10→N11.
- N5 requires N2; can run after N2, before N4. N6 requires N3 and N5's artifact schema.
- Do not run implementation subagents in parallel if they modify the same files (`db/models.py`, API, compose, UI). Parallelize only read-only audits.
- N3 is a hard gate for N6/N9; if no continuity, stop district scope and deliver municipal national with explicit limitation.

## Review Focus tests

1. District vs municipality/plan tests in N3, N6, N9.
2. Coverage and unmatched tests in N3, N6, N10.
3. National volume/streaming tests in N2, N4, N7, N11.
4. Mixed-level/plan rejection in N1, N7, N9.
5. Missing data/new keys in N2, N3, N6.

## Self-review

- [ ] Spec §1–16 mapped to N1–N11; no scope without task.
- [ ] Every task has files, interfaces, RED/GREEN and commit; no undefined type.
- [ ] Critical gates: 98/95 coverage, 2023 plan, no cross-level sum, `state_code=all`, page/JSON limits.
- [ ] Plan proportion: tasks, not implementation transcripts.
- [ ] Unknowns: ACCDB continuity is a phase-1 research dependency; if unavailable, N3/N6/N9 are blocked, not guessed.

## Approval and execution

El usuario aprobó el diseño y el plan, y eligió ejecución por agentes con **ChatGPT Luna**; si se agotan los tokens, **Gemini 3.8 Flash**. La implementación comienza en un worktree nuevo, no en `main` ni en la rama de diseño. Cada tarea tendrá implementador y revisor independientes; la compuerta N3 se evalúa antes de N6/N9.
