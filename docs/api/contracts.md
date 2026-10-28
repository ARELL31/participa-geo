# Contratos HTTP del MVP

Base y convenciones fijadas para todos los endpoints. El esquema OpenAPI se genera
desde FastAPI (T5); este documento fija las firmas, los schemas Pydantic y los
ejemplos que las pruebas de contrato confrontan. No se mantiene un segundo esquema
manual divergente.

## Convenciones globales

- Prefijo: `/api/v1`. Todas las rutas de negocio viven bajo ese prefijo.
- `Content-Type` de respuestas de datos: `application/json`.
- `Content-Type` de errores: `application/problem+json`.
- Cuerpos JSON de entrada: máximo **32 KiB** (`32768` bytes), excepto `POST /scenarios`
  que admite hasta **128 KiB** (`131072` bytes). Una petición mayor se
  rechaza con `413` antes de parsear. Todos los cuerpos prohíben campos extra
  (`extra="forbid"`) y números no finitos (NaN/Infinito).
- Fechas y horas en **ISO 8601 UTC**.
- Identificadores públicos: **UUID**. Nunca se acepta SQL, CQL o filtros arbitrarios.
- Sin campos libres ni datos personales; el MVP no tiene autenticación.

## Envoltorios comunes

`api/schemas/common.py` define:

```python
class DatasetMeta(BaseModel):
    dataset_version_ids: list[UUID] = []
    reference_date: str = "2025-12-15"
    model_run_id: UUID | None = None
    generated_at: datetime  # UTC
    geographic_warning: str = ""
    filters: dict = {}

class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    meta: DatasetMeta
```

`Page[T]` es el envoltorio de toda lista: `{items, page, page_size, total, meta}`.
`meta` incluye versiones, fuentes/corte y filtros aplicados.

## Errores: `application/problem+json`

Campos estables (todos los errores, salvo que se indique):

| Campo | Tipo | Significado |
|---|---|---|
| `type` | string | URN del tipo de error (`urn:participa-geo:error:*`). |
| `title` | string | Título corto legible. |
| `status` | int | Código de estado HTTP. |
| `detail` | string | Descripción sin trazas privadas, SQL ni credenciales. |
| `instance` | string | Ruta solicitada. |
| `code` | string | Código de máquina estable (`not_found`, `validation_error`, ...). |
| `request_id` | string | UUID de la petición, coincide con la cabecera `X-Request-ID`. |

Extensiones permitidas: el `503` de readiness añade `checks`. No se incluyen
stack traces ni secretos.

Correspondencia de estados:

| HTTP | `code` | Cuándo |
|---|---|---|
| 400 | `bad_request` | Entrada inválida a nivel de protocolo. |
| 404 | `not_found` | Recurso desconocido. |
| 409 | `conflict` | Estado incompatible (p. ej. artefacto institucional no generado). |
| 413 | `payload_too_large` | Cuerpo JSON mayor de 32 KiB. |
| 422 | `validation_error` | Validación de entrada (Pydantic). |
| 429 | `rate_limited` | Límite de creación de escenarios (10/minuto por cliente). |
| 503 | `not_ready` / `unavailable` | Prerequisitos no satisfechos / dependencia no disponible. |

Ejemplo de recurso ausente:

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

## Health

### `GET /health/live`

Proceso responde; no equivale a datos listos. Siempre `200`:

```json
{ "status": "alive" }
```

### `GET /health/ready`

Comprueba prerequisitos: `database`, `migrations`, `dataset`, `model`, `gis`.
Si todos son verdaderos:

```json
{
  "status": "ready",
  "checks": {
    "database": true,
    "migrations": true,
    "dataset": true,
    "model": true,
    "gis": true
  }
}
```

Si falta algún requisito, `503` con `code=not_ready` y la extensión `checks`
indicando los fallos:

```json
{
  "type": "urn:participa-geo:error:not_ready",
  "title": "Servicio no disponible",
  "status": 503,
  "detail": "El servicio no está listo: faltan prerequisitos.",
  "instance": "/api/v1/health/ready",
  "code": "not_ready",
  "request_id": "00000000-0000-0000-0000-000000000003",
  "checks": {
    "database": false,
    "migrations": false,
    "dataset": false,
    "model": false,
    "gis": false
  }
}
```

Hasta que las tareas T2–T5 carguen datos, migraciones, modelo y capas GIS, el
endpoint devuelve `503`. `live` no depende de GIS. No se realizan llamadas HTTP
a sí mismo.

## Rutas de negocio (contrato de referencia, implementación en T5/T6/T9)

| Método/ruta | Contrato |
|---|---|
| GET `/territories` | `state_code=14` (o `all`), `level=municipality`, `q<=80`, `page=1`, `page_size<=500`; `Page[TerritoryDTO]`. |
| GET `/participation/history` | `level=municipality`, `state_code=14` (o `all`), `territory_id?:UUID`, `year?:enum`, `page_size<=500`; `Page[HistoryDTO]`. Distrito devuelve sólo observación 2024. |
| GET `/participation/summary` | `level`, `year=2024`; 32 filas con conteos sumados, riesgo elegible/insuficiente y cobertura por entidad. El color usa abstención observada de conteos. |
| GET `/models`, `/models/{id}` | `level=municipality` (predeterminado); sólo expone el modelo municipal nacional publicado. Un nivel distrital devuelve 409 `district_model_unavailable`; ejecuciones antiguas/no publicadas devuelven 404. |
| GET `/predictions` | `level=municipality`, `model_run_id?:UUID`, `target_year=2027`, `territory_id?:UUID`, `state_code=14` (o `all`); `page_size<=500`. Nivel distrito devuelve 409 `district_model_unavailable`. |
| POST `/scenarios` | `level=municipality`, hasta 1,000 IDs, cuerpo hasta 128 KiB; `201` `ScenarioDTO`. Distritos devuelven 409 `district_model_unavailable`; no hay escenarios distritales. |
| GET `/scenarios/{id}` | `200`/`404`. |
| GET `/recommendations` | `level=municipality`, `state_code=14` (o `all`); reglas explicadas para el modelo municipal nacional publicado. Distrito devuelve 409 `district_model_unavailable`; un nivel inválido o repetido devuelve 422. |
| POST `/reports` | `ReportRequest`; `200` cache/`201` creado/`409`/`413`/`503`. |
| GET `/reports/{id}`, `/reports/{id}/download` | Metadatos/estado y descarga; `404`/`409`. |
| GET `/gis/wms`, `/gis/wfs` | Adaptador validado hacia GeoServer interno (sólo lectura). WMS nacional; WFS por entidad/bbox y máximo 1,000. No se aceptan CQL, REST, Transaction ni URLs. |

Estas rutas se implementan en tareas posteriores; su firma queda fijada aquí para
que el OpenAPI generado y los tipos de cliente no diverjan. Las rutas de lectura y
los escenarios/recomendaciones ya están implementados (T5/T6); reportes y
exportaciones quedan para T9.

## Escenarios

### `POST /scenarios`

Cuerpo exacto (sin campos libres, `extra="forbid"`, números finitos):

```json
{
  "model_run_id": "00000000-0000-0000-0000-000000000001",
  "target_year": 2027,
  "territory_ids": ["00000000-0000-0000-0000-000000000002"],
  "reduction_pp": 3.0,
  "assumption_code": "preventive_exploration"
}
```

Reglas vinculantes:

- `model_run_id` debe ser la ejecución publicada (`get_published_model_run_id`);
  no se acepta un ID de artefacto codificado en el cliente.
- `target_year` es exactamente `2027`.
- `territory_ids`: lista no vacía, sin duplicados y de máximo 125 IDs. Todos deben
  pertenecer a las 125 predicciones publicadas y ser elegibles. Una predicción
  insuficiente no puede seleccionarse; se responde `422` con
  `errors[].territory_id` y `errors[].reason`.
- `reduction_pp` es finito y está entre `0` y `10` puntos porcentuales.
- `assumption_code` es el enum cerrado `preventive_exploration` o
  `model_sensitivity`; su texto explicativo proviene de una plantilla revisada.
  Enviar `rationale_text` u otro campo libre es `422`.

Cálculo de la comparación:

- `A` = abstención estimada 2027 publicada. `B = max(0, A - reduction_pp)` sólo
  para los municipios seleccionados y elegibles; los no seleccionados conservan
  `B = A`; las predicciones insuficientes permanecen `null`/`insufficient`.
- `requested_reduction_pp` es el valor solicitado; `effective_reduction_pp` es
  `A - B` (entre `0` y el solicitado).
- La banda A es el rango de error histórico de referencia. La banda B se obtiene
  trasladando la banda A por la reducción efectiva y recortando a `0–100`; se
  etiqueta como `rango de error histórico de referencia trasladado
  condicionalmente; no es un intervalo causal`. No cuantifica el efecto ni
  agrega evidencia.
- Los umbrales de riesgo son los mismos que para A (`<40`, `40–<50`, `>=50`,
  insuficiente). `risk_unstable` indica que la banda cruza un umbral. No se
  estiman personas ni efectos causales.

Respuesta `201` (`ScenarioDTO`), con exactamente 125 resultados persistidos:

```json
{
  "scenario_id": "00000000-0000-0000-0000-000000000010",
  "model_run_id": "00000000-0000-0000-0000-000000000001",
  "target_year": 2027,
  "requested_reduction_pp": 3.0,
  "assumption_code": "preventive_exploration",
  "assumption_version": "1.0",
  "rationale_text": "Supuesto de exploración preventiva: ...",
  "rules_version": "scenario-rules-1.0.0",
  "input_sha256": "…64 hex…",
  "model_sha256": "…64 hex…",
  "error_band_label": "rango de error histórico de referencia trasladado condicionalmente; no es un intervalo causal",
  "selected_territory_ids": ["00000000-0000-0000-0000-000000000002"],
  "created_at": "2026-10-26T12:00:00Z",
  "results": [
    {
      "territory_id": "00000000-0000-0000-0000-000000000002",
      "municipality_code": "001",
      "municipality_name": "ACATIC",
      "baseline_abstention_pct": 47.0,
      "hypothetical_abstention_pct": 44.0,
      "baseline_error_lower_pct": 45.0,
      "baseline_error_upper_pct": 49.0,
      "hypothetical_error_lower_pct": 42.0,
      "hypothetical_error_upper_pct": 46.0,
      "requested_reduction_pp": 3.0,
      "effective_reduction_pp": 3.0,
      "risk_a": "medium",
      "risk_b": "medium",
      "risk_a_unstable": false,
      "risk_b_unstable": false,
      "selected": true
    }
  ]
}
```

La escritura del escenario y sus 125 resultados es una sola transacción: un fallo
no deja escenario parcial. Se guardan selección, reducción solicitada/efectiva,
código y texto controlados, versiones de supuesto/reglas, hashes de entrada y
modelo, y fecha. No se guarda identidad de creador (el MVP no tiene autenticación).

Límite: **10 creaciones de escenario por minuto por cliente** y **una solicitud
activa por cliente**. Excederlo devuelve `429` `application/problem+json` con
`code=rate_limited` y la extensión `retry_after_seconds`. El limitador es en
memoria y válido sólo para el MVP de un solo worker; no es un límite distribuido.
El mapa de clientes está acotado a **512 claves**: en cada comprobación se eliminan
los clientes cuyo evento más reciente quedó fuera de la ventana y, si se alcanza
el tope, se desaloja el cliente inactivo menos recientemente usado. Así se limita
tanto la memoria como la retención de direcciones de origen.

### `GET /scenarios/{scenario_id}`

Devuelve `200` con el `ScenarioDTO` persistido, sin recalcular ni reentrenar, o
`404` `not_found` si el UUID es desconocido.

## Recomendaciones

### `GET /recommendations`

Filtros equivalentes a `/predictions`: `model_run_id?`, `target_year=2027`,
`territory_id?`, `page>=1`, `page_size=1..125`. Devuelve
`Page[RecommendationDTO]`:

```json
{
  "items": [
    {
      "territory_id": "00000000-0000-0000-0000-000000000002",
      "municipality_code": "001",
      "municipality_name": "ACATIC",
      "target_year": 2027,
      "risk": "high",
      "risk_unstable": true,
      "eligible": true,
      "model_run_id": "00000000-0000-0000-0000-000000000001",
      "rules_version": "recommendation-rules-1.0.0",
      "recommendations": [
        {
          "code": "institutional_review",
          "version": "recommendation-rules-1.0.0",
          "priority": "high",
          "title": "Considerar revisión institucional",
          "action": "Considerar información cívica y revisión institucional; no constituye una obligación ni una asignación de recursos.",
          "reasons": ["risk_high"]
        }
      ]
    }
  ],
  "page": 1,
  "page_size": 25,
  "total": 125,
  "meta": {"reference_date": "2025-12-15", "model_run_id": "…"}
}
```

Las reglas son legibles y versionadas: mejora de calidad de datos cuando la
proporción de no especificados es alta o la predicción es insuficiente,
seguimiento preventivo/institucional según riesgo, monitoreo de categoría
inestable y advertencia de equidad/cobertura. No hay optimización de presupuesto,
perfilado partidista, segmentación persuasiva ni inferencia individual; el texto
proviene de plantillas fijas, nunca de entrada del usuario.

## Reportes y exportaciones

### `POST /reports`

Cuerpo cerrado (`extra="forbid"`); no admite URL, ruta, plantilla ni texto libre:

```json
{
  "kind": "scenario_csv",
  "scenario_id": "00000000-0000-0000-0000-000000000010",
  "territory_id": null,
  "year": null,
  "level": "municipality",
  "district_plan": null,
  "state_code": "all"
}
```

`kind` es el enum cerrado: `history_csv`, `history_xlsx`,
`model_evidence_csv`, `model_evidence_xlsx`, `scenario_csv`,
`scenario_geojson`, `scenario_pdf`, `scenario_map_png`, `scenario_map_pdf`,
`methodology_pdf`, `executive_pdf`, `technical_zip`, `district_observed_pdf`,
`territory_fiche_pdf`, `national_geojson`.

- `scenario_id` es obligatorio para `scenario_*`; en otros tipos se rechaza.
- `territory_id`/`year` aplican a historia y fichas observadas.
- Todas las peticiones incluyen `level` (predeterminado `municipality`),
  `district_plan` y `state_code` (`all` para agregado nacional). La ficha
  `territory_fiche_pdf` presenta municipio o agregado estatal observado 2024.
  La ficha distrital requiere `level=federal_district`, `district_plan=DERFE2023`
  y un `territory_id`; se titula “Observado 2024” y muestra cobertura.
- `national_geojson` requiere un estado concreto (`state_code` de dos dígitos) y
  hasta 1,000 geometrías reales por nivel. El nivel distrital usa DERFE2023 e
  incorpora conteos/cobertura observados en 2024, nunca una predicción.
- Las exportaciones admiten hasta 20,000 filas. Historia distrital sólo publica
  DERFE2023/2024; reportes predictivos y escenarios distritales 2027 se rechazan.
- `model_evidence_*` exporta features 2027, exclusiones por corte y
  contribuciones aditivas M0/M1 por municipio del modelo publicado.
- Las exportaciones pequeñas son síncronas (sin cola, sin `pending`).
- `201` creado; `200` caché por hash de filtros/versiones/modelo/escenario/supuestos.
- `409 institutional_package_not_generated` si `methodology_pdf`,
  `executive_pdf` o `technical_zip` no han sido generados por la CLI. La API no
  los genera ni los encola.
- `429 rate_limited` si hay una exportación activa por cliente o se superan 10
  nuevas por minuto (extensión `retry_after_seconds`).
- `503 unavailable` si GIS falla al componer mapas o si se agota la cuota de
  1 GiB de datos generados (`quota_exceeded`).
- Límites: exportación ≤20,000 filas, escenarios municipales nacionales; mapas 1200×900,
  timeout GIS 5 s, total 30 s, archivo pequeño ≤20 MiB.

Respuesta `ReportArtifactDTO` (nunca incluye una ruta local):

```json
{
  "report_id": "…UUID…",
  "kind": "scenario_csv",
  "format": "csv",
  "status": "ready",
  "size_bytes": 54000,
  "sha256": "…64 hex…",
  "created_at": "2026-10-27T00:00:00Z",
  "download_url": "/api/v1/reports/…/download",
  "filename": "participa-geo-escenario-….csv",
  "cached": false,
  "scenario_id": "…",
  "model_run_id": "…",
  "sources": {}
}
```

### `GET /reports`, `GET /reports/{id}`, `GET /reports/{id}/download`

`GET /reports` devuelve `Page[ReportArtifactDTO]` con los artefactos generados
(institucionales incluidos si existen). `GET /reports/{id}` devuelve metadatos o
`404`. La descarga devuelve el MIME y `Content-Disposition` con hash verificable;
un artefacto desconocido es `404` y uno no disponible es `409`.
