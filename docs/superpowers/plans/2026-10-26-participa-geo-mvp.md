# PARTICIPA-GEO MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar en cuatro jornadas un piloto municipal reproducible de Jalisco que conecte datos CCPC reales, GIS, predicción evaluada, escenarios hipotéticos y los entregables técnicos del Reto 2.

**Architecture:** Monorepositorio con React y un backend FastAPI modular; PostGIS almacena observaciones, geometrías y resultados. GeoServer sólo publica capas WMS/WFS; ETL, entrenamiento y documentación se ejecutan como comandos de la misma imagen Python. Todos los pronósticos se calculan fuera de las consultas HTTP.

**Tech Stack:** Python3.12, FastAPI/Pydantic2, SQLAlchemy2/Alembic/psycopg3, pandas/NumPy/scikit-learn, GeoPandas/Shapely, PostgreSQL/PostGIS, GeoServer; React/TypeScript/Vite, MapLibre, TanStackQuery, Radix, Lucide; pytest, Vitest/TestingLibrary, Playwright/axe; DockerCompose y GitHubActions. ReportLab/openpyxl/matplotlib/Pillow para archivos.

**Spec:** `docs/superpowers/specs/2026-10-26-participa-geo-mvp-design.md` — aprobada por el usuario.

**Estado de ejecución:** plan aprobado por el usuario el 2026-10-26; método elegido: agentes por tarea con revisión independiente y revisión final. Implementación autorizada.

## Global Constraints

- Cobertura: Jalisco,125 municipios; historia2009/2012/2015/2018/2021/2024; objetivo2027 federal intermedia. No judicial2025.
- `LN = SV + NV + NS`; abstención conocida=`100 * NV / (SV + NV)`; participación conocida=`100 * SV / (SV + NV)`; no convertirNS enNV. Denominadorcero retorna `null` con causa.
- Calidad: `SV+NV >= 1000`, `NS/LN <= 0.10`; misma cohorteM0/M1. En retrospectivas exigir calidad de `t,t-3,t-6`; en2027 sólo2021/2024.85 candidatos preliminares, no promesa de cobertura definitiva.
- ReferenciaINE15DIC2025, EPSG:32613→4326 real; WMS3857/WFS4326. Coincidencia de identidad no significa igualdad histórica de límites. `identity_status` separado de `footprint_status`; geometría histórica nullable.
- `StandardScaler`+`Ridge(alpha=1.0)`, seis features especificadas, pesos iguales por municipio. Selección porMAE2021, empateM0. No modificar familia/alpha/umbrales según test2024.
- Rango de error histórico: percentil90 absoluto de errores2021, mínimo30 municipios; no prometer cobertura futura90%. Salidasrecortadas0–100 y frecuencia de recorte documentada.
- Semáforo: bajo<40, medio40–<50, alto>=50, insuficiente si no elegible. Informar inestabilidad cuando el rango cruza umbrales.
- Escenarios: reducción0–10 puntos porcentuales, hasta125 IDs; `assumption_code` enum `preventive_exploration`/`model_sensitivity`; `extra=forbid`. Sin texto libre, datos personales o promesas causales.
- TasasAPI0–100; composición `_share`0–1. UUIDs y UTCISO8601. OpenAPI genera tiposTS; no entrenar porHTTP.
- UnCompose, unpyproject/lockPython, unpackage.json/lockWeb. SinKubernetes, colas, autenticación, tilesexternos obligatorios ni microservicios.
- Exportación:750 filas históricas/125 resultadosescenario; máximo1200x900px por mapa, timeoutGIS5s y total30s;10 operacionesnuevas/minuto/cliente, unaexportaciónactivaporcliente y cuota deartefactos.
- Reportemetodológico10–15 páginasPDF; presentación<=10 diapositivasPDF. ZIPtécnico sin cartas; ZIPfinal privado con firmas incorporadas por el usuario.
- Imágenes y dependencias fijadas; ningún `latest`, secreto oCSVbruto enGit. Sólo loopback; no cambiarfirewall, SELinux o permisosDocker.
- Paleta: Primary#6F1739, Hover#54102A, Secondary#8B1E3F, Accent#AD536D, Background#F7F6F5, Surface#FFFFFF, Text#252525, SecondaryText#666666, Border#E6E0E2; Inter local enUI, Lucide y accesibilidadWCAG2.2AA verificada en los componentes aplicables.
- TDD, commits pequeños y verificaciones reales; no declarar integración, métricas, archivos o accesibilidad listos sin evidencia ejecutada. Avisar antes de descargar imágenes o instalar dependencias de aplicación.

## Review Focus

1. **Cambiar año/municipio rápidamente:** una respuestaHTTP antigua no debe sobrescribir la selección actual ni mezclar historia con objetivo2027. Prueba enT7.
2. **Tasas nulas oNS excesivo:** deben producir informacióninsuficiente, nunca ceros ni números bonitos. Pruebas enT2/T4/T8.
3. **Reejecución/reinicio tras fallo:** ingestión, migración, escenarios y exportaciones deben ser atómicos/idempotentes o informar conflicto, sin duplicados ni archivos parciales. Pruebas enT2/T3/T6/T9.
4. **Coordenadas o filtrosmaliciosos:** no confundirUTMconlon/lat, no exponer administraciónGIS ni aceptarCQL/SQL/URL/plantillas delcliente. Pruebas enT3/T5/T9.
5. **Paquete fuera de esta máquina:** debe funcionar sin `/tmp/opencode`, con fuentes y artefactos trazables; cartas/secretos nunca enAPI/Git/ZIPtécnico. Pruebas enT9/T10.

---

## Resumen de entregas verificables

| Tarea | Entrega | Evidencia mínima |
|---|---|---|
| T1 | Entorno y contratos | Compose validado; health checks y errores tipados comprobados. |
| T2 | Datos reales agregados | Seis años,125 municipios y conciliación de conteos reproducible. |
| T3 | Base y publicación GIS | PostGIS válido; WMS/WFS consultables y de sólo lectura. |
| T4 | Modelo evaluado | Cortes temporales, comparación M0/M1, incertidumbre y exclusiones. |
| T5 | API de consulta | Contratos, paginación, datos/modelos versionados y gateway GIS seguro. |
| T6 | Escenarios y recomendaciones | A/B persistidos, supuestos explícitos y aritmética verificada. |
| T7 | Interfaz territorial | Shell accesible, filtros sincronizados, historia y mapa real. |
| T8 | Interfaz predictiva | Explicaciones, métricas y mapas comparativos sin mensajes causales. |
| T9 | Entregables del concurso | Exportaciones, reporte10–15 páginas, presentación<=10 y ZIP técnico. |
| T10 | Aceptación final | Pruebas integradas, revisión independiente y reproducción limpia. |

## Preparación y estado observado

- Repositorio inicializado sólo con documentación, sin código de aplicación ni dependencias instaladas por el agente.
- DockerEngine29.9.2 y Compose5.6.1 instalados por el usuario. El daemon responde usando `sg docker -c 'docker version'`; grupos de esta sesión aún no incluyen998/docker, aunque la cuenta sí. No se requiere `chmod`, sudo ni nueva membresía.
- En todos los comandos siguientes, si `docker version` devuelve permiso denegado, ejecutar el comandoDocker completo como `sg docker -c '<comando>'`. No modificar el sistema para evitar este detalle de sesión.
- Antes de implementar, conservar este baseline de documentación y crear un worktree con `using-git-worktrees`. Comprobar primero identidadGit existente; si falta, pedir al usuario nombre/correo de autor, no inventarlos. No publicar ni hacerpush sin petición.
- Pruebas e instalación de paquetes se realizarán dentro de imágenes del proyecto. Autorizar descarga de imágenes y dependencias al aprobar la ejecución, tras informar la lista de esteplan.
- Fuentes temporales ya verificadas: `/tmp/opencode/participa-geo-data-research/jalisco-{año}.csv`, `/tmp/opencode/participa-geo-gis/verified-4.dat`. Copiarlas a almacenamiento ignorado de trabajo enT2/T3; **ningún runtime puede depender de esas rutas temporales**.
- Presupuesto orientativo: Día1=T1–T3; Día2=T4–T6; Día3=T7–T9; Día4=T10, revisión y correcciones. Un bloqueo se informa sin sustituir silenciosamente fuentes o metodología.

## Mapa de archivos y contratos compartidos

| Zona | Responsabilidad y archivos principales |
|---|---|
| Entorno | `pyproject.toml`, `uv.lock`, `compose.yaml`, `.env.example`, `.gitignore`, `infrastructure/docker/api.Dockerfile`, `README.md` |
| Backendcomún | `apps/api/participa_geo/{main,settings,cli}.py`, `api/{errors,metadata}.py`, `api/schemas/{common,territories,history,models,scenarios,reports}.py` |
| Datos | `ingestion/{source,schema,aggregate}.py`, `indicators/calculations.py` dentro delpaqueteAPI; `pipelines/ingestion/run.py`; `data/sources.json` |
| Persistencia/GIS | `db/{models,session,repository}.py`, `alembic/`, `gis/geoserver/{bootstrap,security}.py`, `gis/styles/{history,risk}.sld`, `pipelines/validation/geography.py` |
| Predicción | `prediction/{features,cohorts,training,evaluation,artifacts,risk}.py`; `pipelines/training/run.py` |
| API | `api/routes/{health,territories,history,models,predictions,scenarios,recommendations,reports,gis}.py` |
| Escenarios | `scenarios/{rules,service}.py`, `recommendations/rules.py` |
| Frontend | `apps/web/src/{app,components,features,lib,styles}`, `apps/web/{package.json,package-lock.json,vite.config.ts,vitest.config.ts}` |
| Reportes | `reporting/{tables,maps,pdf,delivery,store}.py`; `infrastructure/scripts/{export_openapi,verify_delivery}.py` |
| Pruebas | `tests/{unit,integration,contract,e2e}`, `apps/web/src/**/*.test.tsx`, `tests/e2e/playwright.config.ts` |
| Documentación | `docs/{api,architecture,methodology,design-system,decisions,hackathon}`, fuentes/evidenciayaexistentes |

Las rutas abreviadas de dominioPython de la tabla viven bajo `apps/api/participa_geo/`. No crear archivos vacíos para todos los módulos: crear cada uno cuando su tarea lo necesita. Un único `argparse` enCLI conecta ingestión/migración/entrenamiento/publicación/entrega, sin duplicar lógica en wrappers de pipelines.

### Tipos de dominio y unidades

Definir en las tareas propietarias y reutilizar, no inventar alias incompatibles:

- `MunicipalityKey`: `state_code:str` de2 dígitos y `municipality_code:str` INE de3 dígitos. No concatenar clavesINEGI.
- `MunicipalObservation`: `MunicipalityKey`, `source_version_id:UUID`, `year:int`, `ln/sv/nv/ns:int`, `young_share/senior_share/rural_share:float|None`; tasas y calidad derivadas. T2 lo define en `ingestion/schema.py`.
- `IndicatorValues`, definido en T2 en `indicators/calculations.py`: `participation_pct:float|None`, `abstention_pct:float|None`, `unknown_share:float|None`, `ns_lower_pct:float|None`, `ns_upper_pct:float|None`. `unknown_share` es fracción 0–1; su presentación porcentual multiplica por100. No usar un mismo campo para ambas unidades.
- `QualityDecision`: `eligible:bool`, `reasons:list[str]`, `identity_status:IdentityStatus|None`, `footprint_status:FootprintStatus|None`. T2 deja los estados geográficos enNone; T3 los completa antes del entrenamiento. None nunca significa identidad verificada: impide publicar una predicción hasta completar esa revisión. Razones estables: `zero_denominator`, `small_known_count`, `high_unknown_share`, `invalid_counts`, `ambiguous_identity`, `known_administrative_change`, `missing_lag`, `insufficient_error_history`. T2/T3/T4 amplían sólo la parte que poseen.
- `PredictionRecord`: `territory_id:UUID`, `target_year:Literal[2027]`, `estimated_abstention_pct:float|None`, `historical_error_lower_pct/upper_pct:float|None`, `risk:Literal['low','medium','high','insufficient']`, `risk_unstable:bool`, `quality:QualityDecision`, `model_run_id:UUID`. T4 lo define en `prediction/artifacts.py`; DTOAPI lo reutiliza o adapta explícitamente.
- `DatasetMeta`: `dataset_version_ids:list[UUID]`, `reference_date:'2025-12-15'`, `model_run_id:UUID|None`, `generated_at:datetimeUTC`, `geographic_warning:str`, `filters:dict`. T1 lo define en `api/schemas/common.py`; no secretos.
- `Page[T]`: `{items:list[T], page:int, page_size:int, total:int, meta:DatasetMeta}`. Predicciones/territoriospage_size<=125; historiapage_size<=125 y exportación dehistoria<=750. Orden estableINEnumérico.
- Identificador de referencia reproducible: `uuid5(NAMESPACE_URL, 'ine:14:municipality:{code3}:2025-12-15')`. Origen: `uuid5(NAMESPACE_URL, 'ccpc:14:municipality:{code3}:{year}')`. Dataset y modelo identificados por hash de contenido; no UUID aleatorio para reproducibilidad de joins.
- `ScenarioComparison` y `ScenarioDTO` exponen `results:list[ScenarioResult]`; cada resultado conserva `territory_id` y los campos A/B indicados en el contrato. T6 define estos tipos en `api/schemas/scenarios.py` y los usa en dominio y respuesta, sin duplicar fórmulas en frontend.
- `tests/conftest.py` pertenece a T1 y define las fixtures HTTP base; cada tarea añade allí sólo sus fixtures necesarias. Las integraciones usan exclusivamente una base PostGIS de pruebas identificada y aislada, nunca SQLite ni una base de usuario.

### Contratos HTTP a fijar antes de implementar rutas

Prefijo `/api/v1`. `docs/api/contracts.md` fija estas firmas, schemasPydantic y ejemplos; `docs/api/openapi.json` se genera desdeFastAPI, nunca se mantiene un segundo esquema manual divergente.

| Ruta | Parámetros/resultado esencial |
|---|---|
| GET `/health/live` | `200 {status:'alive'}` |
| GET `/health/ready` | `200 {status:'ready',checks:{database,migrations,dataset,model,gis}}`;503 usaProblemDetail, code `not_ready` y extensión `checks` con los fallos. No hacer llamadasHTTP a sí mismo. |
| GET `/territories` | `state_code='14',level='municipality',q<=80,page=1,page_size=25`; `Page[TerritoryDTO]` con `id,name,state_code,municipality_code,identity_status,footprint_status,reference_date`. |
| GET `/participation/history` | `territory_id?:UUID,year?:enum[2009,2012,2015,2018,2021,2024],page,page_size`; `Page[HistoryDTO]`. Sinmunicipio produce seisagregadosestatales, no medias de tasas. |
| GET `/models`, `/models/{id}` | Familia, parámetros, cohortes, features, hashes, metadatosdisponibilidad y métricasM0/M1 por2021/2024. |
| GET `/predictions` | `model_run_id?:UUID,target_year=2027,territory_id?:UUID,page,page_size`; `Page[PredictionRecord]`,125 registros incluyendoinsuficientes. |
| POST `/scenarios` | `ScenarioRequest`;201 `ScenarioDTO` completo, con125 resultados para comparaciones estatales y selección indicada. |
| GET `/scenarios/{id}` | Escenario persistido o404. GETesidempotente, no recalcula/entrena. |
| GET `/recommendations` | Filtros depredicción y paginación; reglas explicadas, versión y motivos. |
| POST `/reports` | `ReportRequest`;201 creado/200cache;409 si faltaartefactoinstitucional;413 tamaño;503GISno disponible. |
| GET `/reports/{id}` | `ReportArtifactDTO` con estado `ready|failed`, formato, tamaño, hash yURLdedescarga;404desconocido. |
| GET `/reports/{id}/download` | Archivo con MIME/Content-Disposition y hash;409fallido; sinpath delcliente. |
| GET `/gis/wms`, `/gis/wfs` | Adaptadorvalidado delAPI haciaGeoServerinterno. Permite sóloGetCapabilities/GetMap/GetFeatureInfo/GetFeature con capas y parámetros deallowlist, noREST/admin/WFS-T/URL/SQL/CQLdelcliente. |

`ScenarioRequest` exacto:

```json
{
  "model_run_id": "00000000-0000-0000-0000-000000000001",
  "target_year": 2027,
  "territory_ids": ["00000000-0000-0000-0000-000000000002"],
  "reduction_pp": 3.0,
  "assumption_code": "preventive_exploration"
}
```

LosUUIDdel ejemplo son exclusivamente documentación, no IDs reales ni fixtures deproducción. `territory_ids` no vacía, única y<=125; todos conocidos/elegibles. La comparación conserva los125 municipios: B=A en no seleccionados; insuficientes permanecennull. Resultado por municipio: `baseline_abstention_pct`, `hypothetical_abstention_pct`, `requested_reduction_pp`, `effective_reduction_pp`, bandastraducidas, riesgoA/B y condición deselección.

`ReportRequest`: `{kind,scenario_id?:UUID,territory_ids?:list[UUID]}`; `kind` enum `history_csv,history_xlsx,scenario_csv,scenario_geojson,scenario_pdf,scenario_map_png,scenario_map_pdf,methodology_pdf,executive_pdf,technical_zip`. Escenario obligatorio para tipos `scenario_*`. Selección vacía explícita es422; campo omitido significa estado. Metadatos/fuentes/modelo obligatorios en archivos; clasificación nula no se exporta como cero. `scenario_csv` concreta la exportación tabular de resultados A/B ya requerida por el diseño; no añade un nuevo módulo.

Error exacto — ejemplo de recursoausente:

```json
{
  "type": "urn:participa-geo:error:not_found",
  "title": "Recurso no encontrado",
  "status": 404,
  "detail": "El recurso solicitado no existe.",
  "instance": "/api/v1/scenarios/00000000-0000-0000-0000-000000000001",
  "code": "not_found",
  "request_id": "00000000-0000-0000-0000-000000000003"
}
```

`Content-Type: application/problem+json`; sinstacktraces, SQL ocredenciales. Todos los cuerposJSON prohíben campos extra y números no finitos. EntradasJSON<=32KiB; solicituddemasiadogrande413 antesdeparsear. No nombres personales ni campos libres.

---

## Task 1: Entorno reproducible y contrato mínimo de servicio

**Files:**
- Create: `pyproject.toml`, `uv.lock`, `compose.yaml`, `.env.example`, `.gitignore`, `README.md`.
- Create: `infrastructure/docker/api.Dockerfile`, `infrastructure/docker/db-init.sh`.
- Create: `apps/api/participa_geo/{__init__,main,settings,cli}.py`, `api/{errors,metadata}.py`, `api/schemas/common.py`, `api/routes/health.py`, `tests/conftest.py`.
- Create: `docs/api/contracts.md`, `docs/architecture/dependencies.md`.
- Test: `tests/unit/test_settings.py`, `tests/contract/test_health.py`, `tests/integration/test_compose_security.py`.

**Interfaces:**
- Consumes: diseñoaprobado, DockeryComposeaccesibles; sinstackprevio.
- Produces: `create_app(settings:Settings|None=None)->FastAPI`; `Settings` validado; `ProblemDetail`, `DatasetMeta`, `Page[T]`; CLI `python -m participa_geo.cli --help`; contenedorapi condependenciasdev.

- [ ] **Step 1 — Fijar contrato y dependencias sin arrancar producto:** escribir `contracts.md` conforme alapartadoanterior; declarar sólo bibliotecas usadas por elplan. Verificar tags de Python3.12, Node24, `postgis/postgis:17-3.6` y `docker.osgeo.org/geoserver:2.28.6` enregistros/oficiales y fijardigests. Estasdosúltimasfamilias están documentadasactualmente; si eltagespecífico no existe, investigar antesde elegiralternativa. Registrarlockgenerado, licencias y descargas previstas; no elegirimágenesantiguas3.5 sinparches porcostumbre.
- [ ] **Step 2 — Escribir pruebas rojas de configuración/HTTP:** `test_missing_secret_rejected` exigeSettings falle si faltaDBpassword; `test_live_is_alive` exige200/statusalive; `test_ready_without_dataset_is_503` exige503 ychecksfalse; `test_validation_uses_problem_json` exige422 ycamposestables. Importar `participa_geo.main` inexistente debe fallar antesdecrear implementación.

```python
def test_ready_without_dataset_is_503(client_without_dataset):
    response = client_without_dataset.get('/api/v1/health/ready')
    assert response.status_code == 503
    assert response.json()['checks']['dataset'] is False
```

- [ ] **Step 3 — Ejecutar y registrar RED:** construir sólo el entorno de pruebas Python con pyproject/lock y ejecutar `docker compose run --rm --no-deps api pytest tests/unit/test_settings.py tests/contract/test_health.py -q`. La imagen inicial instala dependencias con `uv sync --frozen --all-groups --no-install-project` y configura `PYTHONPATH=/workspace/apps/api`; esto permite que el primer fallo sea por el módulo de producto aún inexistente, no por intentar empaquetarlo prematuramente. Antes del primer build avisar al usuario que se descargarán imágenes y dependencias contenidas, sin instalaciones host.
- [ ] **Step 4 — Implementar mínimo:** Settingsporvariables, factoryFastAPI, manejadorProblemDetail, request_id/logsJSONredactados, readinessmediantechecksinyectables yCLIargparse. Composeinicialapi/db/geoserver conredinterna, volúmenesnombrados y sinpuertosDB/GIShost; APIsólo127.0.0.1:8000 temporalmente. `SKIP_DEMO_DATA=true`, credencialesGISobligatorias yheap<=1GB; noextensiondescargada alarranque. LímitedeJSON32KiB e importacioneslivianas sinentrenamiento. db-initcrear rolesseparadoswriter/api/gis a partirdevariables, nuncaimprimirsecretos.
- [ ] **Step 5 — Verificar GREEN y seguridad declarativa:** repetirpytest; ejecutar `docker compose config --quiet` y `docker compose run --rm --no-deps api pytest tests/integration/test_compose_security.py -q`. Testinspeccionaconfigsinsecretos, compruebaDB/GISsinhostports, nodefaultpasswords, imágenesdigest y redes. La pruebahealth no demuestraGISfuncional.
- [ ] **Step 6 — Documentar y commit:** READMEsecciónentorno, versiones, comandosprobados y pendientes. `git add` sóloarchivostarea, revisar `git diff --cached --check` y `git diff --cached`, commit `build: establish reproducible API and GIS environment`.

## Task 2: Ingestión oficial, agregación municipal y controles de calidad

**Files:**
- Create: `apps/api/participa_geo/ingestion/{source,schema,aggregate}.py`, `indicators/calculations.py`.
- Modify: `apps/api/participa_geo/cli.py`, `.gitignore`.
- Create: `pipelines/ingestion/run.py`, `data/sources.json`, `docs/methodology/data-dictionary.md`, `docs/methodology/quality.md`.
- Test: `tests/unit/test_ccpc_schema.py`, `tests/unit/test_indicators.py`, `tests/unit/test_aggregation.py`, `tests/integration/test_official_data.py`.

**Interfaces:**
- Consumes: pyproject/Settings/CLI deT1; inventario ychecksums en `docs/methodology/evidence/`.
- Produces: `read_ccpc(path:Path,expected_year:int)->Iterator[CCPCRow]`; `aggregate_municipal(rows:Iterable[CCPCRow])->list[MunicipalObservation]`; `calculate_indicators(ln:int,sv:int,nv:int,ns:int)->IndicatorValues`; `assess_quality(observation:MunicipalObservation)->QualityDecision`.
- CLI: `ingest --source-dir data/raw/ccpc --output-dir data/processed` crea `municipal-observations.parquet`, `quality.json`, `provenance.json` atómicamente; `--fetch` obtienefuentesverificadas si faltan. NormalizacióncodeINE a3dígitos conservaorigen.

- [ ] **Step 1 — Escribir pruebas rojas con fixtures sintéticos aislados:** `test_ns_is_not_abstention` exige para LN100/SV40/NV40/NS20: participación50, abstención50, unknown_share0.20 y cotas40..60; `test_zero_denominator_is_null` exigeNone; `test_aggregates_counts_not_mean_rates` exige participación `(90+1)/(100+10)*100`, no `(90+10)/2`. `test_quality_boundary` acepta LN2000/SV900/NV900/NS200 (10% desconocido,1800 conocidos), rechaza LN2000/SV899/NV900/NS201 y también LN999/SV500/NV499/NS0. Añadir `test_del_missing_is_retained` y `test_duplicate_key_rejected`.

```python
def test_ns_is_not_abstention():
    result = calculate_indicators(ln=100, sv=40, nv=40, ns=20)
    assert result.abstention_pct == 50.0
    assert result.unknown_share == 0.20
    assert (result.ns_lower_pct, result.ns_upper_pct) == (40.0, 60.0)
```

- [ ] **Step 2 — Ejecutar RED:** `docker compose run --rm --no-deps api pytest tests/unit/test_ccpc_schema.py tests/unit/test_indicators.py tests/unit/test_aggregation.py -q`; fallo esperadofuncionesnoimplementadas.
- [ ] **Step 3 — Implementar contrato:** allowlistexacta16columnas, tiposenterosnonegativos, identidadcontable, año yentidad14, sección/tiposecciónU/M/R, sexo0/1(histórico) y0/1/2(2024), edad>=18. ConservarDELnullable yedadalta, agrupar100+ sinrecodificardatosbrutos. Detectarduplicados y no inferircategoríasausentes. SumarLNparashares18–29/60+/R; no usarelectoresSV comodenominadordemográfico. `source.py` verificaSHA-256 delmiembro yCRCZIP; rangosHTTPsiadmitidos, alternativaZIPcompletoconverificación; rutasZIPseguras y límitesdetamaño. Nuncaextraerarchivosarbitrarios.
- [ ] **Step 4 — Ingerir fuentes reales y registrar evidencia:** copiarCSVverificados a `data/raw/ccpc/jalisco-{year}.csv` ydiccionariosdesdeinventario; manifiestoindicaURLnacional, nombremiembro, SHA256CSVyfecha/available_atnullable. Ejecutar `docker compose run --rm --no-deps api python -m participa_geo.cli ingest --source-dir data/raw/ccpc --output-dir data/processed`. Esto requieremontajesespecíficosdatavolúmenes, noDockerSocket.
- [ ] **Step 5 — Verificar GREEN, idempotencia y datosreales:** repetirunitarias ycomandoingest dosveces; `test_reingest_same_hash_no_duplicates` exigeidénticosagregados/hash. Ejecutar `docker compose run --rm --no-deps api pytest tests/integration/test_official_data.py -q`; exige750observaciones,125municipios/año,2999641filasfuente,2953DELnulos2024 ytotalesLNdelatabladeevidencia. Aún no afirmar temporalidadgeográficaconstante.
- [ ] **Step 6 — Documentar y commit:** diccionario, universoCCPC, faltantes, edadesaltas yexclusiones; `git check-ignore data/raw/ccpc/jalisco-2024.csv` debeconfirmarignorado. Commit `feat: ingest and validate official municipal CCPC data`, sinbrutosenGit.

## Task 3: Persistencia PostGIS, correspondencias y publicación GeoServer

**Files:**
- Create: `apps/api/participa_geo/db/{models,session,repository}.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial.py`.
- Create: `gis/geoserver/{bootstrap,security}.py`, `gis/styles/{history,risk}.sld`, `pipelines/validation/geography.py`.
- Modify: `apps/api/participa_geo/cli.py`.
- Create: `docs/architecture/data-model.md`, `docs/methodology/geographic-reference.md`, `docs/decisions/0001-geographic-reference.md`.
- Test: `tests/integration/test_postgis.py`, `tests/integration/test_geography.py`, `tests/integration/test_geoserver.py`.

**Interfaces:**
- Consumes: MunicipalObservation/calidad/provenance deT2; geometríaINEZIP15DIC2025 yuuid5reglas.
- Produces: `Repository(session:Session)` con `upsert_dataset(version:DatasetVersion)->UUID`, `upsert_observations(rows:Sequence[MunicipalObservation])->int`, `get_territories(*,state_code:str,q:str|None,page:int,page_size:int)->tuple[list[TerritoryRecord],int]` y `get_history(*,territory_id:UUID|None,year:ElectionYear|None,page:int,page_size:int)->tuple[list[HistoryRecord],int]`. `DatasetVersion` pertenece a `ingestion/schema.py`; `TerritoryRecord` y `HistoryRecord` pertenecen a `db/models.py` y tienen los campos del DTO correspondiente, sin depender de FastAPI. El nivel territorial es siempre municipal. `import_reference(archive:Path,session:Session)->GeographyAudit` y `publish_layers(settings:Settings)->PublicationAudit` son idempotentes.
- CLI: `db migrate`, `db load --processed-dir data/processed`, `gis import --archive data/raw/gis/ine-jalisco-2025-12-15.zip`, `gis publish`, `gis verify`.

- [ ] **Step 1 — Escribir pruebas rojas deintegración real:** `test_reference_geometry_4326` exige125geometríasválidasSRID4326 ylon/latJalisco(-107..-100,18..23); `test_historical_geometry_is_null` exige750identidadesorigengeometríainexistente; `test_identity_not_footprint_equality` exigeverified_catalogue/not_verified; `test_same_import_is_idempotent` sinfilasduplicadas; APIrole noINSERT yGISrole noUPDATE. `test_wms_and_wfs_read_only` exigeGetMapPNGno vacío/GetFeature125 ytransacciónrechazada.

```python
def test_reference_geometry_4326(postgis_session):
    from sqlalchemy import text
    count = postgis_session.scalar(text('''
        SELECT count(*) FROM territory_version
        WHERE reference_date = DATE '2025-12-15'
          AND geometry IS NOT NULL
          AND ST_SRID(geometry) = 4326 AND ST_IsValid(geometry)
    '''))
    assert count == 125
```

Los nombres SQL de la aserción (`territory_version`, `reference_date`, `geometry`) fijan el contrato de la primera migración. `postgis_session` usa una base de pruebas y limpia únicamente su propia transacción/esquema.

- [ ] **Step 2 — Ejecutar RED:** `docker compose up -d db geoserver`; `docker compose run --rm api pytest tests/integration/test_postgis.py tests/integration/test_geography.py tests/integration/test_geoserver.py -q`. Fallosesperadosschema/capasnoexistentes, noaceptarfixturesSQLlitecomoPostGIS.
- [ ] **Step 3 — Implementar esquema/repositorio eimportación:** tablasespec§10 conchecksconteos, uniques, FK, geometríasource nullable. GeoPandaslecturaZIP y `.to_crs(4326)`, validarShapelyyreportarantesdeintentarcualquierreparación. Nunca `.set_crs(4326)` sobreUTM. Crear125referenciasy750orígenes, correspondencias yestados; persistirdiferenciascatalogos/incidenciasadminsinprobarlímitesiguales. ConsultasSQLAlchemyparametrizadas, transacciónúnicaporimport. GuardargeografíaauditableGeoJSON/GPKGprocesado ychecksums.
- [ ] **Step 4 — Implementar publicación idempotente y seguridad:** workspace `participa_geo`, storePostGISgis_reader, capas `municipalities`, `participation_history`, `predictions`, `scenario_results`. Vistassinlógicapredictiva; filasderesultadosyaalmacenadas. DiseñarSLDhistory/risk coninsuficientegris yleyendaidénticaA/B. ConfigurarWFSBASIC, deshabilitarWFS-T, demo/workspacesajenosfuera yREST/adminsinpublicar. `bootstrap.py` puede usarcredencialadmin sóloadministrativamente enredinterna, sinlogssecretos; reinicio no restablececontraseñas/rolespersonalizadossilenciosamente.
- [ ] **Step 5 — Cargar, publicar y verificar GREEN:** ejecutarmigraciones/load/import/publish yrepetirlos; correrlos3tests. `gis verify` ejecutaGetCapabilitiesWMS/WFS, GetMapEPSG3857 yGetFeatureGeoJSONEPSG4326; validaMIME, bbox,IDs y125geometrías. RegistrarconsultaST_IsValid/ST_SRID yrestriccionespermisos. No contaresteGIScomofuncionalhastaestaprueba.
- [ ] **Step 6 — Documentar y commit:** esquema ydiagramaMermaid, fuentes/corte/CRS, estadosidentidad/huella ylimitaciónaprobada. Commit `feat: publish verified municipal reference through PostGIS and GeoServer`.

## Task 4: Modelo interpretable, validación temporal y artefactos

**Files:**
- Create: `apps/api/participa_geo/prediction/{features,cohorts,training,evaluation,artifacts,risk}.py`, `pipelines/training/run.py`.
- Modify: `apps/api/participa_geo/cli.py`.
- Create: `docs/methodology/model.md`, `docs/methodology/validation.md`, `docs/decisions/0002-model-selection.md`.
- Test: `tests/unit/test_temporal_features.py`, `tests/unit/test_risk.py`, `tests/unit/test_uncertainty.py`, `tests/integration/test_training.py`.

**Interfaces:**
- Consumes: MunicipalObservation, calidad/estadosidentidad deT2/T3 ydatosprocesados.
- Produces: `build_examples(observations:Sequence[MunicipalObservation],target_year:int)->FeatureDataset`; `evaluate_models(dataset:FeatureDataset)->EvaluationBundle`; `train_release(observations:Sequence[MunicipalObservation],output_dir:Path)->ModelBundle`; `classify_risk(value:float|None,eligible:bool)->RiskLevel`; `PredictionRecord`, `ModelBundle` enartifacts.
- Featuresordenexacto: `same_type_abstention_pct`, `previous_abstention_pct`, `previous_young_share`, `previous_senior_share`, `previous_rural_share`, `is_midterm`. `FeatureDataset` incluyeorigenporaño/columna,IDs, exclusionesytargetsoloentrenamiento.
- Artefactos: `model.json`(coeficientes/intercepto/scalerparámetros/salidaspre-recorte/familiaseleccionada), `evaluation.json`, `predictions-2027.parquet`, `exclusions.csv`, `manifest.json`. No `pickle`/`joblib` cargadodesdeAPI. CLI `train --processed-dir data/processed --output-dir data/processed/model`.

- [ ] **Step 1 — Escribir pruebas rojas estadísticas:** `test_features_only_use_t_minus_3_and_6` exigeorigenes2024/2021para2027 yno2027demográficos; `test_common_cohort_for_baseline_and_ridge` exigeIDsidénticosycalidadenlostresaños; `test_scaler_fit_excludes_test_year` sentinel2024 noafectamediastraining; `test_tie_keeps_baseline`; `test_risk_boundaries` exige39.999low/40medium/49.999medium/50high/Noneinsufficient; `test_unknown_quality_never_becomes_zero`; `test_error_band_requires_30` exigeNonecon29 yP90con30, etiqueta no“90%confidence”.

```python
def test_risk_boundaries():
    assert classify_risk(39.999, eligible=True) == 'low'
    assert classify_risk(40.0, eligible=True) == 'medium'
    assert classify_risk(50.0, eligible=True) == 'high'
    assert classify_risk(None, eligible=False) == 'insufficient'
```

- [ ] **Step 2 — Ejecutar RED:** `docker compose run --rm --no-deps api pytest tests/unit/test_temporal_features.py tests/unit/test_risk.py tests/unit/test_uncertainty.py -q`.
- [ ] **Step 3 — Implementar train/evaluate:** seguircortesexactosdelSpec§7, StandardScaler/Ridgealpha1, salidasrecortadas0–100, métricasMAE/RMSE/sesgo/MAEponderado, numeros/cohortes/exclusiones. Selecciónsólo2021; calculo2024despuésdecongelarfamilia. Ajustefinal2015/18/21/24para2027. Si faltanfechaspublicaciónnoafirmarpronósticohistóricooperacional; etiquetarretrospectivaporañodereferencia. No cambiarqualitycutoffparamejorarcobertura.
- [ ] **Step 4 — Ejecutar entrenamiento real:** CLItrain produceartefactos y125registros, con85candidatospendingantesincidenciasadmin yrestoinsuficientes; guardarerrores2021/2024 yP90de2021delafamiliaelegida, cobertura2024desinajuste. Exportarexplicaciónaditiva yrecuadrodecautelano-causal; usarfloat64 ysemilla0paraoperacionesquepermitanaleatoriedad.
- [ ] **Step 5 — Verificar GREEN y reproducibilidad:** repetirunitariasy `docker compose run --rm --no-deps api pytest tests/integration/test_training.py -q`; dosajustesmismosdatos/locks debenigualarfamilia/IDs/exclusiones yvalores con `rtol=0,atol=1e-8`; meta de tiempoexcluida delhashlógico. Mutarobjetivo2024 no cambialaselecciónhechaen2021, aunquesí cambieltest/ajustefinal. No exigirMAEmejorsinoquereflejeelresultado.
- [ ] **Step 6 — Documentar y commit:** tablasderealesmétricas, coeficientes, cobertura ylimitaciones; nuncaescribirresultadosantesdeejecutar. Commit `feat: evaluate interpretable temporal abstention models`.

## Task 5: API de lectura, carga de resultados y gateway GIS

**Files:**
- Create: `api/schemas/{territories,history,models}.py`, `api/routes/{territories,history,models,predictions,gis}.py` bajoelpaqueteAPI.
- Modify: `apps/api/participa_geo/{main,cli}.py`, `db/repository.py`, `api/routes/health.py`.
- Create: `infrastructure/scripts/export_openapi.py`, `docs/api/openapi.json`(generado).
- Test: `tests/contract/test_read_api.py`, `tests/integration/test_read_api_postgis.py`, `tests/unit/test_gis_gateway.py`.

**Interfaces:**
- Consumes: RepositorydeT3, ModelBundle/PredictionRecorddeT4 yPage/ProblemDetaildeT1.
- Produces: rutasGETdelcontratoygateway `/api/v1/gis/{wms,wfs}`; `load_model_bundle(path:Path,session:Session)->UUID`, CLI `model load --bundle-dir data/processed/model`.
- `GeoServerClient.get_map(layer:AllowedLayer,scenario_id:UUID|None,year:ElectionYear|None,bbox:Bounds,width:int,height:int)->bytes` y `get_features(...)` usanhostinternofijoporsettings; noURLentrante.

- [ ] **Step 1 — Escribir pruebas rojas de contrato:** `test_territories_are_stably_paginated` exige125totales y25porpáginapordefecto; `test_history_state_uses_summed_counts`; `test_insufficient_prediction_is_null`; `test_invalid_year_and_page_rejected` para2023/page0/size126; `test_unknown_id_404`; `test_gis_gateway_rejects_cql_and_admin` paraCQL_FILTER/REST/Transaction/URLarbitraria.

```python
def test_gis_gateway_rejects_cql_and_admin(api_client):
    response = api_client.get('/api/v1/gis/wfs', params={
        'request': 'GetFeature', 'CQL_FILTER': 'INCLUDE',
    })
    assert response.status_code == 422
    assert response.headers['content-type'].startswith('application/problem+json')
```

- [ ] **Step 2 — Ejecutar RED:** `docker compose run --rm api pytest tests/contract/test_read_api.py tests/unit/test_gis_gateway.py -q`.
- [ ] **Step 3 — Implementar DTO/rutas y cargatransaccional:** UUIDvalidado, filtrosparametrizados, metadata consistente, publicarsólohistoriaagregada yartefactoautorizado. Si model_run_idnoeselpublicado retornar404/409segúnrecurso, noleerpathsdelcliente. Readinesscompruebamigraciones/datos/modelo/capascon timeoutycachecorta; live nodependedeGIS. Gatewaypermitebboxfinito/ordenado, CRS/filtros/serviciosallowlist ymáximo125features, construyeinternamente filtrosdesdeUUID/año; eliminacredencialesyhostsprivadosdeerrores.
- [ ] **Step 4 — Cargar artefacto y verificar GREEN:** ejecutarmodelloadypytest; integraciónHTTPconPostGIS `docker compose run --rm api pytest tests/integration/test_read_api_postgis.py -q`. CompararvaloresAPI conagregadosypermisosreadonly; `q`maliciosonoproduceSQLnifiltradosecrettest. Repetircargamismahashsincrearotromodeloconcontenidoidéntico.
- [ ] **Step 5 — Exportar contrato y commit:** `docker compose run --rm --no-deps api python infrastructure/scripts/export_openapi.py --output docs/api/openapi.json`; testconfrontaOpenAPIyvaloresdelcontrato. Commit `feat: serve versioned municipal analytics and bounded GIS reads`.

## Task 6: Escenarios persistidos y recomendaciones preventivas

**Files:**
- Create: `scenarios/{rules,service}.py`, `recommendations/rules.py`, `api/schemas/scenarios.py`, `api/routes/{scenarios,recommendations}.py` bajoelpaqueteAPI.
- Modify: `apps/api/participa_geo/db/repository.py`, `main.py`, `docs/api/contracts.md`.
- Test: `tests/unit/test_scenarios.py`, `tests/unit/test_recommendations.py`, `tests/contract/test_scenario_api.py`, `tests/integration/test_scenario_persistence.py`.

**Interfaces:**
- Consumes: prediccionespublicadasT4/T5 ySQLAlchemyRepository.
- Produces: `simulate_scenario(predictions:Sequence[PredictionRecord],request:ScenarioRequest)->ScenarioComparison`; `ScenarioService.create(request:ScenarioRequest)->ScenarioDTO`; `recommend(prediction:PredictionRecord)->list[Recommendation]`.
- Resultados persistidos para125 municipios;25 es únicamente el tamaño predeterminado de páginas de lectura, no un límite de escenarios. Campos DTO alineados con el contrato, IDs UUID, banda por traslación condicional y hash de inputs.

- [ ] **Step 1 — Escribir pruebas rojas:** `test_reduction_is_percentage_points` exigeA47.0,reducción3.0→B44.0; `test_reduction_clips_at_zero` exigeA2/reducción3→B0/reducciónefectiva2; `test_unselected_territories_unchanged`; `test_insufficient_selected_rejected` exige422conIDycausa; `test_duplicate_nan_extra_fields_rejected`; `test_rationale_must_be_catalogue_code`; `test_transaction_failure_leaves_no_partial_scenario`; recomendacióndeNSaltoesmejoradedatos,nooptimizaciónpolítica.

```python
def test_reduction_is_percentage_points(predictions_47_pct, request_3_pp):
    result = simulate_scenario(predictions_47_pct, request_3_pp).results[0]
    assert result.baseline_abstention_pct == 47.0
    assert result.hypothetical_abstention_pct == 44.0
    assert result.effective_reduction_pp == 3.0
```

Las fixtures de esta tarea contienen predicciones sintéticas claramente aisladas: el primer municipio tiene47%, es elegible y está seleccionado en `request_3_pp`; no se cargan en la base de demo.

- [ ] **Step 2 — Ejecutar RED:** `docker compose run --rm api pytest tests/unit/test_scenarios.py tests/unit/test_recommendations.py tests/contract/test_scenario_api.py -q`.
- [ ] **Step 3 — Implementar servicio/rutas:** solicitarlistano-vacía<=125, modelovigenteyobjetivo2027, reduction0–10finita; rechazarantesdeescribir. CalcularB/risks/bandassinreentrenar yguardarA/B/selección/versionesbajounatransacción. Recomendacionesreglasversionadasporrisk/quality/inestabilidad; texto institucionalneutro sinsegmentaciónpersuasiva. Límite10creaciones/minutoporclientecon429ProblemDetail; memoriaacotadaydocumentarvalidezparaunsoloworkerMVP.
- [ ] **Step 4 — Verificar GREEN eintegración:** repetirsuite y `docker compose run --rm api pytest tests/integration/test_scenario_persistence.py -q`; crear, leer, reiniciarAPIyleerotra vez conservaresultados. Compararshaartifactomodeloantes/despuésigual. GetMapcapascenariofiltradoporUUIDcoincideconresultadosDB, sinsuperponerotrosescenarios.
- [ ] **Step 5 — Commit:** actualizarOpenAPIgenerado ycommit `feat: compare hypothetical municipal scenarios with traceable assumptions`.

## Task 7: Application Shell accesible e inteligencia territorial

**Files:**
- Create: `apps/web/{package.json,package-lock.json,index.html,tsconfig.json,vite.config.ts,vitest.config.ts}`, `infrastructure/docker/web.Dockerfile`, `infrastructure/docker/nginx.conf`.
- Create: `apps/web/src/{main.tsx,app/App.tsx,app/filters.ts,app/navigation.ts,lib/api.ts,lib/api.generated.ts,styles/tokens.css,styles/app.css}`.
- Create: `apps/web/src/components/{ApplicationShell,PageState,RiskBadge,DataTable,GeographyNotice}.tsx`, `features/territory/{TerritoryPage,MunicipalMap,HistoryChart}.tsx`.
- Modify: `compose.yaml`; Create: `docs/design-system/README.md`.
- Test: `apps/web/src/app/filters.test.ts`, `features/territory/TerritoryPage.test.tsx`, `components/ApplicationShell.test.tsx`, `tests/e2e/territory.spec.ts`.

**Interfaces:**
- Consumes: OpenAPIT5/T6 y `/api/v1`/GISgateway; sinfetchdirectoaGeoServeradmin.
- Produces: Shell yconsultaterritorialoperativos; `useGlobalFilters():{territoryId:string|null,historicalYear:ElectionYear,setFilters(next:Partial<GlobalFilters>):void}`; `queryKeys.history(filters)` ykeys que incluyenaño/modelo; `api.generated.ts` creadopor `openapi-typescript`, noeditadoamanualmente.
- Helpers de filtros en `app/filters.ts`: `parseFilters(params:URLSearchParams):GlobalFilters`, `serializeFilters(filters:GlobalFilters):URLSearchParams`. Un año desconocido produce `RangeError`; el shell lo captura y ofrece restablecer filtros, no una página en blanco. `GlobalFilters={territoryId:string|null,historicalYear:ElectionYear}`.
- Rutas: `/`resumen, `/territory`, `/prediction`, `/scenarios`, `/reports`. Seccionesavanzadas muestran“Pendiente”, sinfalsasnavegacionesoperativas. `target_year=2027` separadoy fijo.

- [ ] **Step 1 — Consultar UIUXProMax y fijartokens:** usarbúsquedadirigida `"keyboard focus filters" --domain ux` yguíasReact; noadoptarplantillascommercialesnimodificarpaletaaprobada. Documentarshell, escalatipográfica, espacios4/8, bordesdiscretos, focodecontraste3:1 ytexto4.5:1; Interlocalconlicencia. AñadirsólodependenciasReact/Vite/TS/MapLibre/TanStackQuery/RadixDialog/Lucide/@fontsource-inter ydevtools requeridas; sinshadcncompletosóloportenerlo.
- [ ] **Step 2 — Escribir pruebas rojas deUI:** `test_filter_state_round_trips_url` conservaUUID/año yrechaza2023; `test_late_response_does_not_override_current_selection` invierteordenrespuestas yexigeque permanezcalaselecciónmásreciente; `test_shell_keyboard_and_pending_modules` verificafoco/movil ypendientesinacción; `test_history_null_shows_unavailable` exigeetiqueta,no0; `test_geometry_notice_always_visible` exige“Referencia cartográfica: diciembre de2025”.

```ts
it('round trips the global historical filters', () => {
  const filters = { territoryId: null, historicalYear: 2021 as const }
  expect(parseFilters(serializeFilters(filters))).toEqual(filters)
  expect(() => parseFilters(new URLSearchParams('year=2023'))).toThrow(RangeError)
})
```

Dependencies de pruebas web: Vitest, jsdom, TestingLibrary React/jest-dom/user-event y MSW para simular orden de respuestas sólo en unitarias. Las integraciones E2E no reemplazan la API real por MSW.

- [ ] **Step 3 — Ejecutar RED:** añadirserviciowebComposeycontenedordevtestNode24conlock; `docker compose run --rm --no-deps web npm run test -- --run`. Fallosesperadosporcomponentesfaltantes, noentornodenavegadorroto.
- [ ] **Step 4 — ImplementarShell, URL yconsulta:** controlesnativosetiquetadoscuandoalcancen, RadixDialogparasiderbarmóvilconretornodefoco. TanStackQueryporfiltrosconAbortSignal; nuncamostrarresultadoanteriorcomoactualsinaviso. MapaMapLibreconWMSgatewayyWFSvalidado, selecciónpormunicipios ybotonestablaalternativa; fondoneutrosintilesexternos. GráficohistóricoSVGsimpleconlíneaytablapara6años, sinbibliotecadegráficosredundante. ContarNSyuniversoconocido; advertirgeografía ydatosinsuficientes. NginxproxyaAPIyGISgatewaymismoorigen, sólohost127.0.0.1:8080; quitarpuertohostAPItrasverificaresteservicio.
- [ ] **Step 5 — Verificar GREEN yflujo básico:** unitarias, `npm run typecheck`, `npm run build` encontenedor; Playwrightterritoryseleccionamunicipio/año ycontrastaindicadorytablaAPI; teclaTabyEnter, menúmóvil375px, 320pxreflow yzoom200%. Mapafallido conservaaccesotabularconerror, nopantallavacía.
- [ ] **Step 6 — Commit:** registrarcontrasteychecksmanualesrealizados; commit `feat: add accessible territorial application shell and historical map`.

## Task 8: Predicción explicable y comparación visual de escenarios

**Files:**
- Create: `apps/web/src/features/prediction/{PredictionPage,ModelComparison,PredictionExplanation}.tsx`, `features/scenarios/{ScenarioPage,ScenarioForm,ScenarioMaps,ScenarioTable}.tsx`, `features/executive/ExecutivePage.tsx`.
- Modify: `apps/web/src/app/App.tsx`, `lib/api.generated.ts`(regenerar), `styles/app.css`.
- Test: `apps/web/src/features/prediction/PredictionPage.test.tsx`, `features/scenarios/ScenarioPage.test.tsx`, `tests/e2e/scenarios.spec.ts`.

**Interfaces:**
- Consumes: Shell/GlobalFiltersT7, modelos/prediccionesT5 yescenarios/recomendacionesT6.
- Produces: vistamodeloconMAE2021/2024/cobertura/explicación, formulariohipotéticoacotadoy125resultadosA/B; compartirURLconscenario_idsinsecretos. `historicalYear` nocambiahorizonte2027.

- [ ] **Step 1 — Escribir pruebas rojas:** `test_prediction_is_not_observation` exigeetiquetasdistintas; `test_insufficient_is_not_zero_or_green`; `test_model_metrics_keep_validation_and_test_separate`; `test_baseline_winner_is_honestly_explained`; `test_hypothesis_requires_catalogue_assumption`; `test_scenario_selected_only_and_same_legend`; `test_band_is_historical_error_not_causal_interval`.

```tsx
it('labels insufficient risk instead of showing low risk', () => {
  render(<RiskBadge risk="insufficient" />)
  expect(screen.getByText('Información insuficiente')).toBeVisible()
  expect(screen.queryByText('Riesgo bajo')).not.toBeInTheDocument()
})
```

Texto de controles del simulador: `Municipios`, `Reducción hipotética (puntos porcentuales)`, `Supuesto`, `Crear escenario` y `Exportar CSV`. Usar un select múltiple nativo para la selección municipal inicial y un input numérico accesible para puntos porcentuales; no introducir un selector complejo sólo por estética.

- [ ] **Step 2 — Ejecutar RED:** `docker compose run --rm --no-deps web npm run test -- --run src/features/prediction src/features/scenarios`.
- [ ] **Step 3 — Implementar páginas:** porcentajesconunidades, riesgocontexto+icono, rangoerrorhistórico/inestabilidad, comparaciónM0/M1noconfundirvalidaciónconcerteza. Mostrarcontribucionesaditivasdelfamiliaelegidasinclasificarcausas. Formulario0–10pp, catálogo, municipioslegiblesyeligible; confirmacióndesupuestosantesdePOSTyresultadopersistido. MapasladoaladoA/Bconmismoleyenda/corte, cámaraopcionalmentesincronizada ytablaporcentajeA/B/diferencia. Enmóvilapilarvistas sinperderfiltros. ResumenejecutivoderivadeAPI, noestático. AccionesdeexportaciónaúnpendientesdeshabilitadashastaT9conexplicación.
- [ ] **Step 4 — Verificar GREEN yPlaywright:** unitarias/tipos/build; `scenarios.spec.ts` crea3pp conmunicipioelegible, exigeB=A-3o0segúnborde, persistealrecargar ynoalterahistoria; recorrerinsuficientes, error422 yfallored. RevisiónUIUXProMaxsobrecomponentesyaimplementados, conalternativatabular yfocusvisible.
- [ ] **Step 5 — Commit:** `feat: expose model evidence and clearly hypothetical scenario comparisons`.

## Task 9: Exportaciones, reporte metodológico y presentación ejecutiva

**Files:**
- Create: `reporting/{tables,maps,pdf,delivery,store}.py`, `api/schemas/reports.py`, `api/routes/reports.py` bajoelpaqueteAPI.
- Create: `apps/web/src/features/reports/{ReportsPage,ExportActions}.tsx`.
- Modify: `apps/api/participa_geo/{cli,main}.py`, `apps/web/src/app/App.tsx`, `features/scenarios/ScenarioPage.tsx`, `docs/api/openapi.json`(regenerar).
- Create: `docs/hackathon/{report-outline,executive-outline,delivery-checklist,source-licenses}.md`, `infrastructure/scripts/verify_delivery.py`.
- Test: `tests/unit/test_exports.py`, `tests/integration/test_report_api.py`, `tests/integration/test_delivery.py`, `tests/e2e/exports.spec.ts`.

**Interfaces:**
- Consumes: datosagregadosT2/T3, ModelBundleT4, ScenarioDTOT6 yGeoServerClientT5; mapa eUIyaoperativos.
- Produces: `export_history(rows:Sequence[HistoryDTO],kind:Literal['csv','xlsx'],meta:DatasetMeta)->bytes`; `export_scenario_csv(scenario:ScenarioDTO,meta:DatasetMeta)->bytes`; `render_scenario_map(scenario:ScenarioDTO,kind:Literal['png','pdf'])->bytes`; `generate_methodology(context:DeliveryContext)->bytes`; `generate_executive(context:DeliveryContext)->bytes`; `build_technical_zip(context:DeliveryContext,output:Path)->DeliveryManifest`.
- `ReportStore.get_or_create(request:ReportRequest)->ReportArtifactDTO` atómico/hashcache; límites1activa/cliente,10nuevas/minuto, cuota1GiBdatosgenerados (fuentesignoradasnoseborran). `DeliveryContext` contienevaloresreales, fuentes/modelo/escenarioyatribuciones, nuncatemplate/URLdelusuario.
- CLI: `deliver --scenario-id UUID --output-dir dist/hackathon --team-slug participa-geo`; `verify-delivery --archive PATH`. Seexcluye `dist`deGit.

- [ ] **Step 1 — Escribir pruebas rojas dearchivo:** `test_csv_xlsx_preserve_nulls_and_versions` y`test_spreadsheet_formula_text_is_escaped`; `test_geojson_matches_scenario_and_reference` exige125geometrías4326/corte/porcentajes ynullsinsuficientes; `test_map_failure_is_not_placeholder_success`; `test_failed_export_leaves_no_partial_file`; `test_export_limits_and_cache`; `test_institutional_missing_is_409_not_pending`; `test_unknown_paths_and_urls_rejected`; `test_technical_zip_excludes_private_files` confixtures de.env/cartas/credencialesquedebenquedarfuerasiempre.

```python
def test_methodology_page_count(delivery_context):
    from io import BytesIO
    from pypdf import PdfReader
    report = generate_methodology(delivery_context)
    assert 10 <= len(PdfReader(BytesIO(report)).pages) <= 15
```

La fixture `delivery_context` recoge versiones, escenario y métricas obtenidas por las tareas previas; los documentos finales se verifican también con datos reales, no sólo con fixtures de maquetación.

- [ ] **Step 2 — Ejecutar RED:** `docker compose run --rm api pytest tests/unit/test_exports.py tests/integration/test_report_api.py -q`.
- [ ] **Step 3 — Implementar exportacionespequeñas yUI:** CSV/XLSXmunicipalconhojadiccionario/metadatos; GeoJSONA/Bmismafuentegeométrica; GetMapA/Binternos1200x900timeout5s, componerleyenda/fechas/modelo/advertencia enPNG/PDF. Cancelar/fallar si total>30s, detectarWMSServiceExceptionaunqueHTTP200, validarbytes/MIMEymax20MiBarchivopequeño. Cacheporhashincluyefiltros/versiones/supuestos, escrituraaarchivotemporal+rename; sinworker/colaniestadopending. UIgenera/descargaexportacionespequeñassinoperador; controlesbloqueanduplicadosymuestranerrores. No devolverrutaslocales dearchivos.
- [ ] **Step 4 — Implementar documentosinstitucionalesyZIPCLI:** reporteobjetivo12páginasA4 (aceptar10–15) conloscontenidosSpec§13 yresultadosreales; presentación9diapositivas (aceptar<=10), archivosPDF. CargarfuenteTTFlocalconlicenciaverificada(InteroSourceSans3), sininstalarfuenteshost. Mismastablas/modelo/escenarioenUIePDF. ZIPtécnicoallowlistcon6CSVJaliscooficiales, ZIPGISoriginal,diccionarios, datosprocesados, artefactos, código/docs/checksums, sin.git/node_modules/cache/.env/cartas. Revisarfuentes/condicionesredistribuciónantesdeincluir: si noestánclaras, informarbloqueoypediralternativa, sinasumirpermiso. Documentarexcepcióndearchivosfuenteagregadoscongranularidadoriginalyprohibicióninferenciapersonal. CartasfirmadasseintegransóloporelusuariofueraAPI/contenedores/repopúblico.
- [ ] **Step 5 — Verificar GREEN, documentos y descargas:** repetirpytest; ejecutardeliverconescenariorealy `docker compose run --rm api pytest tests/integration/test_delivery.py -q`. `pypdf`cuenta10–15/<=10páginas, extraetextoconsources/modelo/supuestosysemanfororecomendaciones; XLSXabreyGeoJSONvalida. Playwrightexportsdescargahistoria, escenario yPDFmapeado; CSVdatoscoincidenconAPI, PNGnoestávacío. VerificarZIPyhashsinnecesidadde`/tmp/opencode`.
- [ ] **Step 6 — Revisar y commit:** revisarmetodologíaredactada, no sólo contar páginas; `docs/hackathon/delivery-checklist.md` separaconfirmacióntécnica yfirmas/cesión/envíohumanos. Commit `feat: generate reproducible institutional reports and technical delivery package`.

## Task 10: CI, ensayo limpio y aceptación final

**Files:**
- Create: `.github/workflows/ci.yml`, `tests/e2e/playwright.config.ts`, `tests/e2e/full-journey.spec.ts`, `tests/e2e/accessibility.spec.ts`, `docs/hackathon/verification-results.md`, `docs/architecture/deployment.md`.
- Modify: `README.md`, `docs/superpowers/fase0-checklist.md`, `docs/hackathon/delivery-checklist.md`, `compose.yaml`(perfilesdetests), `apps/web/package.json`(scripts).

**Interfaces:**
- Consumes: todosloscontratos yarchivosT1–T9.
- Produces: evidenciaejecutabledeMVP, CIreproducible, ZIPtécnicoautocontenido, manualdeinstalación/despliegueloopback ylistadebloqueosadministrativos.
- SuiteE2EusaaplicaciónrealconPostGISyGeoServer; mocksMSWsóloenunitariasFrontend. Playwright/Chromium dentrodeimagen Nodecondependenciasfijadas,1workerpararespetar~8GBRAM.

- [ ] **Step 1 — Escribir pruebas deaceptación antesdelajustefinal:** fulljourneyseleccionamunicipio/año→historia→predicción→3pp→A/B→CSV/XLSX/GeoJSON/PDF; otroflujoinsuficienteimpidecrearintervenciónsobreeseID. Accessibilityexigefocoetiquetas/teclado, axe sinviolacionescritical/serious, layout320/375/1440, reducemotion, zoom200%; inspecciónmanualdelector/focodocumentadaapartesinpretenderautomatizacióntotalAA.

```ts
test('exports a real scenario without an operator', async ({ page }) => {
  // The setup for this test creates an eligible scenario through the real API.
  await page.goto(`/scenarios?scenario_id=${scenarioId}`)
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Exportar CSV' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/\.csv$/)
  expect(await download.failure()).toBeNull()
})
```

Para este test `scenarioId` se obtiene en `test.beforeEach` mediante `/api/v1/scenarios` con un municipio elegible consultado a la API, no con un ID inventado. Leer además el CSV y contrastarlo con el escenario persistido. `Exportar CSV` usa el tipo `scenario_csv` y la función `export_scenario_csv` definidos antes de implementar en el contrato y T9.

- [ ] **Step 2 — Ejecutar y registrar fallos reales:** `docker compose --profile test run --rm e2e npx playwright test --config tests/e2e/playwright.config.ts`; registrarquécriteriosfallan, noalterarassertionsparaocultarlos. Si detectabug, systematic-debugging ypruebaregresiónantesdefix.
- [ ] **Step 3 — ConfigurarCI ydocumentaciónoperativa:** workflowsconversionesaccionesfijadas, Pythonruff/pytest yTSeslint/typecheck/Vitest/build; integraciónPostGIS yGISsmoke reales enrunnercuandoalcancememoria, no declararlaspassedsi fueronomitidas. DocumentarpruebaGISlocalcompleta. READMEincluyevariablessecretas,volúmenes,migraciones,ingestión,entrenamiento,publicación,reportes,limitaciones2025/85candidatos y“noautenticación/localonly”; confirmarcapacidadmedida/healthchecks/logsrotados. Noabrirpuertos/firewall.
- [ ] **Step 4 — Ensayo limpio aislado:** extraerZIPtécnicoaunnuevodirectorioclaramentenombrado, usar `docker compose -p participa_geo_cleanroom ...` conpuertolocaldistinto8081yvolúmenespropios; **no** borrarvolúmenesdeltrabajo. Validarchecksums, arrancar,migrar,cargaryreentrenarconfuentesempaquetadas (sindescargasINE ni `/tmp/opencode`). Compararfamilia/exclusiones/prediccionesconatol1e-8; permitirinternet sóloimágenes/paquetes. Pararyretirarsóloelstackcleanroomcreadoporestaoperación, yvolúmenessólodespuésderevisarelnombreyconautorizaciónsi haydudadepropiedad.
- [ ] **Step 5 — Verificaciónfinal explícita:** ejecutarruff,pytestunit/contratos/integración, types/build/Vitest yPlaywrightcompletos; GetCapabilities/GetMap/GetFeatureconvaloresválidos, readiness200ydegradación503alcaerGIS, 403/404adminyTransactionrechazada; verificardocumentospáginas/datos/mapas/ZIP, sinsecretos. Escribir `verification-results.md` concomandos/fechas/resultado/cobertura/exclusiones/limitacionesynoejecutadas. No declarardesplieguepúblico, métricassuperiores oAAcompletosinsoporte.
- [ ] **Step 6 — Revisar rama e integrar según autorización:** solicitar revisión independiente del diff entero y cumplimiento de Spec, resolver hallazgos atendiendo la causa raíz y repetir pruebas afectadas. Si Native, es la primera revisión independiente de código definitivo; si Subagent-driven, se añade a las revisiones por tarea. Commit `test: verify complete institutional analysis and clean-room delivery`. Usar finishing-a-development-branch para presentar opciones de integración; no hacer push/PR ni entrega por email por cuenta propia.

## Contratos de paralelismo y método de ejecución

Camino crítico: T1→T2→T3→T4→T5→T6→T7→T8→T9→T10. Algunasdependenciaspermitenconcurrencia, pero nodebenforzarse antesdeestabilizarinterfaces.

- TrasT2puedenavanzarT3GISyT4modeloenparalelo: T3posee`db/`, `gis/`, integracióngeográfica; T4posee`prediction/` ypruebasestadísticas. T4consumeelcontratoidentidadexistente; sielGIScambiaestados, sevalidaantesdepublicarartefactos. SóloelintegradoractualizaCLI/pyproject/compose paraevitarconflictos.
- TrasT5puedehacerloT6backend mientrasT7frontendconsumecontratoslectura, conarchivosdistintos. SchemaHTTPesinmutable salvoacuerdodelintegrador; regenerateTStrascambios.
- T8esperaT6+T7; T9esperaescenario persistido+GIS; T10esperatodo. No delegar tareas que escribenlosmismosarchivos.

**Recomendación para este plazo:** ejecuciónNative enestasesión, conTDD yrevisiónindependientefinal. Lasdieztareascompartentipos, CLI, datos y contratos; mantenerunimplementadorreducecostedecontextoyconflictos. Investigación puntual/revisiónsípuededelegarse concontratocerrado. Alternativa: Subagent-driven, unimplementadorfrescopor tarea yrevisoresportarea, máscosto/latenciaymásaislamientoderevisión.

## Autorrevisión del plan

- [x] **Cobertura de Spec:** secciones1–3→alcance/T1;4/6→T2;5/10→T3;7/8→T4;11→T1/T5/T6/T9;9→T6/T8;12→T7/T8;13→T9;14→T1/T3/T5/T6/T9/T10;15→T10;16/17→método y gates. No quedaron requisitos del alcance sin tarea; las firmas y el envío final son comprobaciones humanas explícitas.
- [x] **Pasos:** cada tarea identifica archivos, contrato, pruebas RED, implementación, verificación GREEN y commit. Se incluyeron aserciones concretas como código. Se corrigió una fixture incoherente del límite NS para que LN y conteos concilien. No se ejecutaron estas pruebas: todavía son instrucciones del plan.
- [x] **Tipos:** MunicipalObservation/QualityDecision enT2; correspondencia y Repository enT3; PredictionRecord/ModelBundle enT4; Page/ProblemDetail enT1; ScenarioRequest/DTO enT6; ReportRequest/Artifact enT9. Se fijaron firmas del repositorio, unidades de unknown_share, results de escenarios y helpers de filtros. El contrato incluye scenario_csv antes de implementarlo.
- [x] **Review Focus:** cambios rápidos→T7; null/NS→T2/T4/T8; reinicio/atomicidad→T2/T3/T6/T9; CRS/inputs GIS→T3/T5/T9; reproducibilidad/privados→T9/T10.
- [x] **Proporción:** diez entregas revisables, sin centenares de tareas ni cuerpos completos de implementación. La preparación de entorno se agrupa con la entrega que habilita. La longitud del plan es del mismo orden que la especificación; no implica que el producto ya exista.

## Aprobación y entrega del plan

El usuario aprobó el diseño y el plan, y eligió la ejecución con **agentes por tarea** (implementador y revisor independientes) más revisión final del conjunto. La rama se aislará mediante worktree. La autorización de descarga de imágenes/dependencias de aplicación dentro de contenedores quedó implícita al aprobar la ejecución.
