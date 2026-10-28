# Task 11 — Rendimiento, CI, cleanroom y aceptación final

**Status: DONE_WITH_CONCERNS**

## Resultado

- Rendimiento nacional medido contra el stack real en `127.0.0.1:8081`; todos
  los límites quedaron dentro de objetivo:

  | Operación | Primera | p95 caliente | Umbral |
  |---|---:|---:|---:|
  | WMS GetMap 1200×900 | 0.9581 s | 0.9504 s (10 muestras) | ≤5 s frío / ≤2.5 s caliente |
  | WFS state14, count 1000 | 0.3094 s | 0.3428 s | ≤3 s; máximo 1,000 |
  | API municipios state14/page500 | 0.0275 s | 0.0245 s | ≤500 ms |
  | Resumen 32 entidades | 0.0306 s | 0.0239 s | ≤1 s |

- `get_participation_summary` evita la subconsulta correlacionada por observación
  y selecciona una vez el dataset municipal más reciente por estado.
- Se agregaron pruebas de rendimiento reales y una E2E nacional para cobertura,
  nivel/entidad, perfil distrital, `409` de predicción/escenario distrital y
  rechazo de WFS nacional ilimitado. Accesibilidad automatizada pasó; no se
  declara certificación AA.
- CI fue ajustado para unitarias y contratos nacionales que no necesitan DB,
  además de Ruff, ESLint, TypeScript, Vitest y build. **GitHub Actions no fue
  ejecutado** en esta sesión.
- El backend completo quedó **243 passed, 76 skipped, 1 warning**. Los skips de
  fixtures Jalisco de 125 filas se marcaron con motivo de superseded y se
  documentaron; los reemplazos nacionales se ejecutaron. Los dos skips por
  GeoJSON MVP faltante mantienen su motivo explícito.
- Playwright real: **16 passed, 2 skipped**; los skips son dos journeys Jalisco
  antiguos que esperan contratos de 125 filas y fueron reemplazados por la E2E
  nacional. Web: lint/typecheck pasan, Vitest **10 archivos / 67 tests**, build
  pasa con advertencia informativa de chunk MapLibre >500 kB.
- ZIP final generado con CLI y verificado por separado:
  `dist/national/technical.zip`, `complete: true`, 311 miembros verificados,
  `scenario_required: false`, modo `confirm`, **460,317,105 bytes**, SHA-256
  `f30e2cb153ffdc45ca568bc2ea8d9251ceb4f0471eec3a17772af2dcf77faa52`. Se
  comprobó que incluye 6 ZIP CCPC + 32 ZIP MGS y no `.env`, `.git`, cartas,
  credenciales ni datos personales.

## Concern bloqueante: reproducción cleanroom integral

- Se extrajo el ZIP generado al directorio nuevo
  `/tmp/opencode/participa-geo-national-cleanroom-20261028T190000Z`, con Compose
  `participa_geo_national_cleanroom`, puerto 8082 y volúmenes independientes.
  Se construyeron imágenes, migración limpia `0013` y `ingest-national` desde los
  seis CCPC terminaron: 54,872,712 facts / 192 CSV / 14,779 observaciones
  municipales / 300 distritos / 44,154 `DEF` vacíos; cargados a PostGIS.
- `district rebuild` no pudo iniciar: el ZIP no contiene
  `data/raw/continuity/official-section-history.csv`; también faltan ACCDB INE y
  `data/raw/continuity/district-headquarters.txt`. `gis import-national` abortó
  porque no encuentra las 300 etiquetas oficiales. El entrenamiento intentado
  antes del import no encontró referencia MGS (`0/2477` municipios / `0/32`
  estados). Por esto no se afirma `readiness=200`, API/GIS/WMS/WFS, `model load`,
  comparación `atol=1e-8` ni aceptación cleanroom completa.
- El comando legado `db load` también falla sobre el formato nacional por falta
  de `provenance.json`; el CLI `ingest-national` es el cargador nacional y sí
  cargó los facts. No se modificó ese contrato legado.
- El ZIP final vigente se extrajo aparte en
  `/tmp/opencode/participa-geo-national-cleanroom-20261028T203000Z`; sus **312**
  líneas de `CHECKSUMS.sha256` dieron OK y se confirmó que faltan los insumos
  mencionados. La stack cleanroom de la prueba completa se detuvo/eliminó sólo
  con su propio project name y volúmenes. El stack de trabajo no se tocó y
  permaneció listo.
- Para cerrar la preocupación se necesita autorizar/atribuir el empaquetado de
  insumos fuente de continuidad/catálogo o aprobar un rebuild basado en
  evidencia derivada versionada. No se añadió una fuente fuera de las seis CCPC
  y 32 MGS autorizadas.

Evidencia extendida, comandos y límites: `docs/hackathon/verification-results.md`
§12; despliegue: `docs/architecture/deployment.md` §10.

## Commit

`14bbad9 test: verify national coverage, performance and clean-room delivery`

Verificación posterior al commit: backend **243 passed, 76 skipped, 1 warning**
(227.38 s); web **10 archivos / 67 Vitest passed**, lint/typecheck/build pasan;
Playwright **16 passed, 2 skipped** (1.4 min); Ruff y `git diff HEAD --check`
pasan. El stack nacional mantiene readiness 200.

## Continuación 2026-10-28 — insumos de continuidad autorizados

- Estado: **DONE_WITH_CONCERNS**. La fuente INE fue autorizada para esta entrega
  con atribución, URLs y checksums; no se infiere una licencia general de
  redistribución pública.
- ZIP final `dist/national/technical.zip`: **461,133,205 bytes**, SHA-256
  `54fc5d513d44715d6bd49ffd51df9da81fdd8820ec2a69987331bacb393b5cb8`,
  `complete: true`, 315 miembros verificados y 317 entradas de manifiesto.
  Incluye 6 CCPC, 32 MGS, ACCDB, CSV histórico derivado, catálogo de cabeceras y
  `scripts/export_official_section_history.sh`; fuentes/hash revisados y escaneo
  de exclusiones limpio. Se incluye evidencia de atribución, no una licencia
  general de redistribución.
- Backend completo: **248 passed, 76 skipped, 1 warning** (236.67 s). Los 76
  skips están auditados en `docs/hackathon/verification-results.md` §12. Una
  primera invocación aislada con `docker compose run` dejó cuatro pruebas de
  latencia sin el API local (ConnectionRefused); la repetición correcta con
  `docker compose exec -T api pytest -q -rs` pasó. Ruff y Compose config pasan.
- Web: ESLint y typecheck pasan; Vitest **10 archivos / 67 tests**; build
  aprobado con aviso informativo de MapLibre >500 kB. Playwright real:
  **16 passed, 2 skips superseded** (41.7 s). El aviso MSW de handlers no usados
  aparece en Vitest, pero los tests relacionados pasaron. GitHub Actions no se
  ejecutó.
- Cleanroom aislado: `/tmp/opencode/participa-geo-national-cleanroom-20261028T203500Z`,
  Compose `participa_geo_national_cleanroom`, volúmenes propios; migración desde
  cero hasta `0013` e ingesta completa: 54,872,712 hechos / 192 CSV / 14,779
  observaciones municipales / 300 distritos / 44,154 `DEF` vacíos.
- `continuity build` y `district rebuild` pasaron: histórico 75,895 filas; 73,268
  secciones MGS; 2,581 pares municipio/distrito; 72 municipios divididos; cero
  discrepancias CCPC/MGS de referencia; cobertura nacional 2024
  0.9513343123732259, estado `insufficient`.
- `gis import-national` y `publish-national` pasaron. Publicados 32 archivos,
  32 entidades, 2,477 municipios, 300 distritos, 73,268 secciones y capas
  `states`, `municipalities`, `districts_2023`; WFS BASIC, transacciones
  rechazadas. La primera llamada REST autenticada expiró; tras disponibilidad,
  autenticación respondió 200. No bloqueó el reintento.
- Identidad: 2,477 referencias, 14,779 orígenes/correspondencias verificadas,
  cero ambiguas. Entrenamiento M0 run
  `0e288804-1c44-523e-a4a3-7a7db70e8c77` (1,623 candidatos / 2,477 municipios) y
  `model load-national` pasaron.
- Readiness cleanroom 200 con database/migrations/dataset/model/GIS en true;
  predicciones state14 200 / 125 filas; proxy WMS/WFS 200. `gis verify-national`
  completo: GetMap PNG 8,137 bytes, WFS estatal 125 entidades, límite 1,000 y
  transacción rechazada.
- Paridad baseline/rebuild a `atol=1e-8`: estructura/parámetros del modelo,
  exclusiones byte-idénticas (162,546 bytes), 2,477 predicciones y 2,477 filas
  de escenario; máximo delta en modelo, predicción y escenario **0.0**.
- Se preservaron los volúmenes del stack nacional de trabajo; readiness 200 tras
  Playwright y después del teardown. Se eliminaron contenedores, red y volúmenes
  únicamente del proyecto cleanroom. Sigue pendiente la revisión humana
  metodológica/cartas; este resultado se registra en el commit solicitado (sin
  push). Detalle: §13 de `docs/hackathon/verification-results.md`.

## Fix round 1 — revisión Task 11 (2026-10-28)

- Se reemplazó la parte de permisos del módulo Jalisco saltado con
  `tests/integration/national/test_national_roles.py`: cinco pruebas contra la
  base de integración con esquema/datos nacionales. Verifican que `api` no
  inserta/actualiza tablas de origen/resultados y sí consulta agregados;
  `gis_reader` sólo tiene lectura en objetos GIS y no puede actualizar
  `territory_version`; `writer` puede escribir agregados, pero no migrar ni
  administrar el servidor. El skip legacy sigue aplicándose a las diez
  aserciones de datos Jalisco.
- El p95 se corrigió a nearest-rank `ceil(0.95*n)-1`, con pruebas esperadas 95
  para `1..100` y 10 para `1..10`.
- README ahora enumera comandos exactos en el orden ingest → continuity build →
  district rebuild → GIS import → entrenamiento/carga, y enlaza a la metodología.
- Verificación completa: Ruff pasó; backend **255 passed, 76 skipped, 1
  warning**; web ESLint/typecheck/build pasaron y Vitest fue **67/67 en 10
  archivos**; Playwright **16 passed, 2 skipped** (journeys legacy reemplazados).
  GitHub Actions no se ejecutó. Permanecen avisos no bloqueantes de
  Starlette/TestClient, requests MSW no manejadas en tests aprobados, y chunk
  MapLibre mayor a 500 kB.
- ZIP de entrega regenerado y verificado tras incluir README/tests/docs. Sus
  detalles: `dist/national/technical.zip`, **461,135,945 bytes**, **316 miembros
  verificados**, `complete: true`, modo `confirm`, sin escenario requerido;
  SHA-256 `c52b4710602f5667974260788a60402226f60d74c168e2e0dd5e4ec2ab203274`.
  Se confirmó en el inventario la presencia de los tests nacionales y del README
  actualizado. Cleanroom no se repitió por ser cambios de pruebas/documentación;
  la verificación cleanroom previa sigue en §13 de resultados y no es evidencia
  de una nueva corrida en esta ronda.

## Fix round 2 — revisión final de distrito (2026-10-28)

- Los 300 agregados observados 2024 ahora se calculan directamente desde hechos
  CCPC por `DEF`/DERFE2023 en `agg_district_year`, sin depender de MGS ni de la
  continuidad geométrica. Se mantienen por separado los agregados
  municipio×distrito MGS y `district_reconstruction_coverage`. `district rebuild`
  rehizo los artefactos y la persistencia; los 450 sectores CCPC sin MGS aportan
  4,785,314 LN observada.
- Reconciliación tras rebuild: los 300 distritos suman LN 98,330,348, SV
  54,899,228, NV 37,105,466 y NS 6,325,654, exactamente igual al total de los
  hechos CCPC 2024. El endpoint de historia, verificado después del reinicio de
  API, devolvió los mismos 300 registros/conteos y cobertura separada en los 300.
- La ficha distrital explica que el universo de conteos incluye todas las
  secciones CCPC asignadas al DEF2023, mientras cobertura es conciliación MGS.
  Verificación live generó/descargó PDF de 2,665 bytes; ambos textos fueron
  encontrados. `DERFE2021` fue rechazado por la API con HTTP 422 y mensaje que
  exige DERFE2023. La validación también aplica a exportaciones históricas a
  nivel distrital; cache rules subió a `1.1.0`.
- Migración aditiva `0014` agrega `agg_district_year` y permisos de lectura API /
  escritura writer. Se añadieron regresiones para agregación sin MGS,
  reconciliación al CCPC, cobertura independiente, chain/grants y rechazo del
  plan viejo. Pruebas focales: 49 pasaron. Backend completo: **262 passed, 76
  skipped, 1 warning**; web: ESLint, TypeScript, build y **67 tests / 10
  archivos**; Playwright: **16 passed, 2 skipped**. Ruff y `git diff --check`
  pasaron. El warning restante es la deprecación Starlette/TestClient.
- Cleanroom completo no se repitió: el modelo, sus entradas/artefactos y
  predicciones municipales no cambiaron; el cambio afecta observaciones
  distritales y validación de informes. En vez de presentarlo como cleanroom,
  se ejecutaron la reconciliación real de 300 distritos contra los hechos CCPC,
  la regresión de cobertura MGS independiente y la prueba live de historia/PDF/
  HTTP 422. La aceptación cleanroom previa permanece como evidencia histórica,
  no como corrida de esta ronda.
- `dist/national/technical.zip` y su `DELIVERY.json` se regeneraron después de
  estos cambios. Verificación independiente: `complete: true`, 318 miembros,
  modo `confirm`, sin escenario requerido; 461,140,043 bytes; SHA-256
  `c210132c3b2623f40e67c7eebb170fa0c8543c2e5eb7dcaeb698602e37a45045`.
  Se confirmaron en el inventario la migración `0014`, las pruebas de regresión,
  `district-observations.csv`, metodología y verificación-results actualizados.
- Estado sigue `DONE_WITH_CONCERNS`: GitHub Actions no ejecutado y revisión
  humana metodológica/cartas pendiente. No se generó ninguna predicción
  distrital 2027.

## Corrección de verificación — endpoint de pruebas de rendimiento (2026-10-28)

- La revisión final detectó que el módulo de rendimiento usaba loopback del
  contenedor y una variable antigua. `BASE_URL` ahora lee
  `NATIONAL_API_BASE_URL` y por defecto usa `http://web:80` (proxy nginx de
  Compose); los paths y umbrales permanecen intactos.
- La falla se reprodujo antes del cambio en un contenedor efímero Compose: los
  dos casos API recibieron `ConnectionRefusedError` al acceder a 127.0.0.1:8000.
  Ejecución corregida dentro de la red nacional:
  `sg docker -c 'docker compose run --rm --no-deps --entrypoint pytest api -q tests/integration/national/test_performance.py'`
  → **6 passed, 1 warning**. Suite backend completa:
  `sg docker -c 'docker compose exec -T api ruff check . && docker compose exec -T api pytest -q -rs'`
  → Ruff pasó; **262 passed, 76 skipped, 1 warning**.
- Cambio sólo en configuración de pruebas/documentación; ningún producto,
  modelo o artefacto predictivo cambió. No se repitió cleanroom completo por
  esta corrección test-only. El ZIP se regeneró y verificó tras actualizar los
  tests/docs: `complete: true`, 318 miembros, 461,140,408 bytes; SHA-256
  `f8beafd005d7b563f572b62a8c8c6347aa64428b2da09a67ea7af746cc5141e1`.
  También figura en `dist/national/DELIVERY.json`.
