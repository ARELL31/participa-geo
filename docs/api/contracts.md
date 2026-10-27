# Contratos HTTP del MVP

Base y convenciones fijadas para todos los endpoints. El esquema OpenAPI se genera
desde FastAPI (T5); este documento fija las firmas, los schemas Pydantic y los
ejemplos que las pruebas de contrato confrontan. No se mantiene un segundo esquema
manual divergente.

## Convenciones globales

- Prefijo: `/api/v1`. Todas las rutas de negocio viven bajo ese prefijo.
- `Content-Type` de respuestas de datos: `application/json`.
- `Content-Type` de errores: `application/problem+json`.
- Cuerpos JSON de entrada: máximo **32 KiB** (`32768` bytes). Una petición mayor se
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
| GET `/territories` | `state_code=14`, `level=municipality`, `q<=80`, `page=1`, `page_size=25`; `Page[TerritoryDTO]`. |
| GET `/participation/history` | `territory_id?:UUID`, `year?:enum`, paginación; `Page[HistoryDTO]`. |
| GET `/models`, `/models/{id}` | Ejecuciones ya entrenadas; sin endpoint de entrenamiento. |
| GET `/predictions` | `model_run_id?:UUID`, `target_year=2027`, `territory_id?:UUID`; `Page[PredictionRecord]`. |
| POST `/scenarios` | `ScenarioRequest`; `201` `ScenarioDTO`. |
| GET `/scenarios/{id}` | `200`/`404`. |
| GET `/recommendations` | Filtros de predicción; reglas explicadas. |
| POST `/reports` | `ReportRequest`; `200` cache/`201` creado/`409`/`413`/`503`. |
| GET `/reports/{id}`, `/reports/{id}/download` | Metadatos/estado y descarga; `404`/`409`. |
| GET `/gis/wms`, `/gis/wfs` | Adaptador validado hacia GeoServer interno (sólo lectura). |

Estas rutas se implementan en tareas posteriores; su firma queda fijada aquí para
que el OpenAPI generado y los tipos de cliente no diverjan.
