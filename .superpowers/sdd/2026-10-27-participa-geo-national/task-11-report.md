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
- ZIP final `dist/national/technical.zip`: **461,133,213 bytes**, SHA-256
  `7f1524b99ed4e17f64c87fd78b419816ae4e6756861c9e3479409313366db636`,
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
