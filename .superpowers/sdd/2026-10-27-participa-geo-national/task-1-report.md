# Task 1 — Dominio, esquema y migración de niveles

**Estado:** DONE_WITH_CONCERNS
**Rama:** `feat/national-expansion`

## Implementación

- Añadidos `TerritoryLevel`, `DistrictPlan`, `TerritoryKey`, `territory_id`, `observation_id` y validación de scope de escenarios en `apps/api/participa_geo/territory.py`.
- Se preserva la forma UUID municipal Jalisco ya publicada. Las identidades de observación municipales conservan la forma histórica con dataset; las distritales incorporan plan y dataset.
- `territory_version` ahora distingue nivel/código/plan y vigencias; `municipality_code` acepta nulo en distritos. `observation`, `model_run`, `prediction`, `scenario` y `scenario_result` llevan nivel/plan con constraints e índices.
- Añadida `0004_national_levels.py`, compatible con el esquema anterior y con una instalación limpia. La migración completa las claves municipales sin recalcular ni modificar IDs; asigna plan sólo a filas distritales que lo tengan explícito.
- DTOs de territorio, historia, modelo y predicción exponen campos aditivos con defaults compatibles con payloads municipales anteriores. `ScenarioRequest.level` queda opcional y tipado; la frontera de dominio rechaza selección cruzada de nivel/plan.
- Añadidos tests unitarios de identidad, validación de claves, mezcla de escenarios, compatibilidad de payloads/OpenAPI DTO y test Postgres de backfill/preservación de IDs.

## TDD y verificaciones

RED:

1. `python -m pytest tests/unit/national/test_territory.py -q` → no se pudo iniciar en el host: `/usr/bin/python: No module named pytest`.
2. `sg docker -c 'docker compose run --rm api python -m pytest tests/unit/national/test_territory.py -q'` → RED esperado: colección falló porque aún no existía `participa_geo.territory`.

GREEN y verificaciones posteriores:

- `sg docker -c 'docker compose run --rm api python -m pytest tests/unit/national/test_territory.py tests/integration/national/test_migration_levels.py -q'` → **10 passed**, 1 aviso deprecado de Starlette/httpx.
- `sg docker -c 'docker compose run --rm api ruff check apps/api/participa_geo/territory.py apps/api/participa_geo/db/models.py apps/api/participa_geo/api/schemas/common.py apps/api/participa_geo/api/schemas/territories.py apps/api/participa_geo/api/schemas/history.py apps/api/participa_geo/api/schemas/models.py apps/api/participa_geo/api/schemas/scenarios.py alembic/versions/0004_national_levels.py tests/unit/national/test_territory.py tests/integration/national/test_migration_levels.py'` → **All checks passed**.
- `sg docker -c 'docker compose run --rm api alembic upgrade head'` → migraciones `0001` a `0004` aplicadas en la DB nacional vacía.
- `sg docker -c 'docker compose run --rm api alembic current'` → `0004 (head)`.
- `git diff --check` → sin errores.
- `sg docker -c 'docker compose run --rm api python -m pytest -q'` → **121 passed, 21 failed, 82 errors**. El conjunto completo no queda verde en este worktree porque faltan los artefactos MVP (`data/processed/municipal-observations.parquet`, `data/processed/model/*`, `data/raw/ccpc/jalisco-2009.csv`) y la capa municipal publicada en GeoServer; esos fallos afectan pruebas de contratos/integración/exportación que dependen de los datos cargados. El test de migración añadido y las pruebas focalizadas sí pasan.

## Límites y observaciones

- No se tocaron ingestión, GIS, modelos predictivos, UI ni reportes.
- No se truncaron ni eliminaron datos o volúmenes; se aplicó la migración a la DB nacional vacía. No se modificó el worktree MVP.
- El suite completo requiere los artefactos de datos y el despliegue de GIS del MVP, ausentes en este worktree, para validar regresión end-to-end.
- El reporte vive en `.superpowers/`, excluido por `.gitignore`; se entrega en el path solicitado y no se fuerza al commit.

## Commit

`feat: add national territory levels and plan-aware identities`

## Fix round 1

### Cambios

- `ScenarioService.create` ahora valida el nivel explícito contra el modelo publicado, comprueba que cada ID seleccionado existe en el universo cargado, conecta `validate_scenario_territories` al flujo y exige que el universo persistido sea compatible con nivel/plan del modelo. Las selecciones mezcladas y los desacuerdos fallan con `ScenarioInputError` antes de escrituras; la ruta existente lo transforma a HTTP 422 `application/problem+json`.
- Si se omite `level`, el servicio infiere nivel/plan del modelo publicado; las solicitudes municipales heredadas siguen admitidas. Nivel/plan se llevan a la comparación, DTO de escenarios y filas persistidas.
- `Repository` lee el nivel/plan del modelo y de los territorios asociados a predicciones, y escribe scope en scenario/result. Los DTOs de modelo/predicción exponen esos valores.
- Añadidos seis casos ejecutando `ScenarioService.create`: nivel municipal explícito compatible, distrito DERFE2023 compatible, nivel explícito distinto, nivel mezclado, planes DERFE mezclados y nivel omitido.
- Añadida prueba PostgreSQL que ejecuta la cadena Alembic real `0001→0003`, reproduce en el esquema aislado la forma anterior a 0004, carga un UUID municipal legado y ejecuta `0004`; comprueba revisión `0004` y preservación del UUID/backfill.
- Alembic `env.py` admite una conexión suministrada por harness, para que el test ejecute la cadena en un esquema aislado sin tocar el esquema público ni otras bases.

### TDD y verificaciones de Fix round 1

- RED: `sg docker -c 'docker compose run --rm api python -m pytest tests/unit/national/test_scenario_scope.py -q'` → **5 failed** inicialmente por el campo de scope faltante en `PredictionRecord`; tras añadir el contrato, la misma ruta de creación fue completada y probada con expectativas de aceptación/rechazo.
- GREEN enfocado: `sg docker -c 'docker compose run --rm api python -m pytest tests/unit/national/test_scenario_scope.py tests/unit/national/test_territory.py tests/integration/national/test_migration_levels.py tests/unit/test_scenarios.py -q'` → **30 passed**, 1 aviso deprecado de Starlette/httpx.
- Cadena real: `sg docker -c 'docker compose run --rm api python -m pytest tests/integration/national/test_migration_levels.py::test_actual_alembic_chain_from_empty_schema_preserves_legacy_identity -q'` → **1 passed**, ejecuta `0001→0003`, prepara una fila municipal heredada y actualiza a `0004`.
- Suite completa: `sg docker -c 'docker compose run --rm api python -m pytest -q'` → **128 passed, 21 failed, 82 errors**.
- Clasificación de fallos de suite: **0 fallos causados por regresiones/aserciones de código**. Las 21 fallas de aserción se explican por recursos ausentes: 18 dependen de artefactos MVP de ingestión/modelo/exportación (`data/processed/municipal-observations.parquet`, `data/processed/model/*`, `data/raw/ccpc/jalisco-2009.csv`); 3 son pruebas GeoServer (`test_wms_getcapabilities_lists_municipalities`, `test_wms_and_wfs_read_only`, `test_wfs_transaction_rejected`) porque la capa publicada `municipalities` no existe en el GeoServer levantado. Los 82 errores restantes son setup/fixtures que requieren esos mismos datos procesados y cargados. El detalle de errores aparece en `tests/contract/test_read_api.py`, `tests/contract/test_scenario_api.py`, `tests/integration/test_*` y pruebas de exportación que cargan artefactos del MVP.
- Advertencia no bloqueante repetida: Starlette informa que el uso de httpx en `TestClient` está deprecado.

### Alcance

Fix round 1 no descarga ni genera los artefactos faltantes ni publica capas GIS; esos pasos quedan fuera de la corrección solicitada. No se usó subagente, `sudo`, instalación host ni cambios al worktree MVP.
