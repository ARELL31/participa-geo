# Resultados de verificación — PARTICIPA-GEO

> **Aceptación nacional Task 11 (actualizada 2026-10-28):** estado
> `DONE_WITH_CONCERNS`. El stack nacional real cumple los límites medidos de
> rendimiento; backend y Playwright quedan verdes con pruebas Jalisco obsoletas
> explícitamente superseded. El ZIP nacional está completo y hasheado. El ensayo
> cleanroom se ejecutó desde el ZIP pero **se bloquea** al faltar en éste los
> insumos de continuidad distrital requeridos por `district rebuild`/`gis import`
> (detalle §12); no se declara reproducción completa.

**Fecha de la corrida:** 2026-10-27 (UTC), rama `feat/participa-geo-mvp`.
**Alcance:** aceptación técnica del MVP local. No es un despliegue público, no
es una certificación AA y no sustituye la revisión humana ni la firma/envío de
cartas. El CI está configurado pero **no se ejecutó en GitHub Actions** en esta
sesión.

## 1. Entorno

| Elemento | Valor |
|---|---|
| Host | AlmaLinux 10.2 (WSL2), x86_64, 7.7 GiB RAM |
| Docker Engine / Compose | 29.9.2 / 5.6.1 |
| Python de la imagen | 3.12.12 (uv 0.9.30, lock congelado) |
| Node / Playwright | Node 24 (imagen fijada), Playwright 1.64.1, Chromium |
| PostgreSQL/PostGIS | `postgis/postgis:17-3.6` (digest fijado) |
| GeoServer | 2.28.6 (digest fijado), WFS nivel BASIC |
| Modelo | M0, `832b21e9-775a-5a74-9b3b-66b923de4e62` (fix wave) |
| Escenario de entrega | `e7c36d5e-b751-4586-89dc-39bca122e892` |
| Referencia cartográfica | 2025-12-15, EPSG:4326, `footprint_status=not_verified` |

`docker compose config --quiet` → **0**.

## 2. Backend

```sh
sg docker -c 'docker compose run --rm --no-deps api ruff check .'
# All checks passed!

sg docker -c 'docker compose run --rm --no-deps api pytest -q'
# 214 passed, 1 warning in 132.62s
```

Cobertura: unitarias, contratos y integración real con PostgreSQL/PostGIS,
Alembic, GeoServer, entrenamiento determinista, exportaciones y verificación del
ZIP. La única advertencia es la deprecación de `httpx`/`starlette.testclient`
(`StarletteDeprecationWarning`), no un fallo.

## 3. Frontend

```sh
sg docker -c 'docker compose run --rm --no-deps -v "$PWD/apps/web:/app" web-test npm run lint'
# ESLint: 0 problemas
sg docker -c 'docker compose run --rm --no-deps -v "$PWD/apps/web:/app" web-test npm run typecheck'
# tsc --noEmit: sin errores
sg docker -c 'docker compose run --rm --no-deps -v "$PWD/apps/web:/app" web-test npm run test -- --run'
# 8 archivos, 50 tests passed
sg docker -c 'docker compose run --rm --no-deps -v "$PWD/apps/web:/app" web-test npm run build'
# vite build OK; bundle principal 402.97 kB, MapLibre 1,062.95 kB
```

El aviso de Vite sobre chunks >500 kB es informativo (MapLibre); no falla el
build. En la primera corrida tras instalar ESLint/axe, un test de `ScenarioPage`
agotó sus 10 s por contención de la suite; la repetición y la corrida final
pasaron 50/50. No se modificó ninguna aserción.

## 4. E2E de producto y aceptación

```sh
sg docker -c 'docker compose --profile tools run --rm --no-deps web-e2e npx playwright test'
# 17 passed (22.7s)

sg docker -c 'docker compose --profile test run --rm e2e npx playwright test \
  --config tests/e2e/playwright.config.ts'
# 17 passed (41.9s)
```

Ambas suites usan la aplicación real (nginx → FastAPI → PostGIS/GeoServer). No
usan MSW. La suite de aceptación (`tests/e2e/`) recorre municipio/año → historia
→ predicción → escenario 3 pp → A/B → descargas CSV/XLSX/GeoJSON/PDF/Mapa PDF y
compara los valores con la API y el escenario persistido. Otro flujo comprueba
que un municipio insuficiente no aparece en el formulario y que `POST` devuelve
`422 ineligible_territory`.

Accesibilidad automatizada del mismo suite:

- axe WCAG 2.0/2.1 A+AA en `/`, `/territory`, `/prediction`, `/scenarios`,
  `/reports` y el diálogo móvil: **0 violaciones critical/serious**.
- Foco visible, skip link, orden de tabulación y activación con Enter.
- Etiquetas accesibles en Municipio, Año histórico, Municipios, Reducción,
  Supuesto y botones de exportación.
- Reflow sin desbordamiento horizontal a 320/375/1440 px.
- `prefers-reduced-motion`: animaciones ≤0.001 s, una iteración, scroll auto.
- Zoom 200% aproximado con viewport 640 CSS px y `body.zoom=2`.

### Hallazgos de la primera corrida (no ocultados)

1. La primera corrida de aceptación encontró 4 fallos:
   - tres páginas con `<dl>` que contenían `<p>` dentro de los `div` de KPI
     (axe `only-dlitems`, serious);
   - la expectativa del CSV de historia pedía 6 filas cuando la exportación
     filtrada por año devuelve 1.
   Se corrigió el marcado (`<dd class="kpi__note">` con estilo propio), se
   corrigió la expectativa al contrato real y se repitió: **17/17**.
2. El primer `deliver` de la sesión agotó el timeout de 5 s de un GetMap de
   GeoServer en frío. `gis verify` respondió 200 con PNG de 73,641 bytes y el
   reintento de `deliver` terminó correctamente. No se cambió el timeout ni se
   ocultó el fallo.

## 5. GIS, salud y bloqueo administrativo

```sh
sg docker -c 'docker compose run --rm --no-deps api python -m participa_geo.cli gis verify'
```

```json
{
  "wms_capabilities_status": 200,
  "wfs_capabilities_status": 200,
  "getmap_status": 200,
  "getmap_png_bytes": 73641,
  "getfeature_status": 200,
  "getfeature_count": 125,
  "municipalities_layer_present": true,
  "wfs_transaction_rejected": true
}
```

Comprobaciones a través del mismo origen (`http://127.0.0.1:8080`):

| Comprobación | Resultado |
|---|---|
| `GET /api/v1/health/ready` | **200** `{database,migrations,dataset,model,gis}=true` |
| GetCapabilities WMS | **200** `text/xml`, capa `participa_geo:municipalities` |
| GetMap WMS (EPSG:3857, 512×512) | **200** `image/png`, 68,557 bytes |
| GetFeature WFS (EPSG:4326) | **200**, **125** features |
| `/geoserver/rest/workspaces` | **404** (nginx bloquea administración) |
| `/api/v1/admin` | **404** problem+json |
| `gis verify` → Transaction | `wfs_transaction_rejected=true` |

Degradación real: se detuvo `geoserver`; tras 5 s, readiness devolvió **503**
`not_ready` con `gis=false` y el resto `true`; se reinició y volvió a **200** con
todos los checks en `true`. No se alteraron volúmenes.

## 6. Paquete técnico final

```sh
sg docker -c 'docker compose run --rm api python -m participa_geo.cli deliver \
  --scenario-id e7c36d5e-b751-4586-89dc-39bca122e892 \
  --output-dir dist/hackathon --team-slug participa-geo \
  --confirm-source-license'

sg docker -c 'docker compose run --rm api python -m participa_geo.cli verify-delivery \
  --archive dist/hackathon/technical.zip'
```

| Dato | Valor |
|---|---|
| `source_mode` | `confirm` (decisión humana de redistribución) |
| `technical.zip` | tamaño y SHA-256 exactos en `dist/hackathon/DELIVERY.json`; no se autoincrusta el hash del propio archivo |
| Miembros del ZIP | **229** (incluye este documento y `exclusions-by-cut.csv`) |
| `complete` | **true** |
| `scenario_required` | true |
| Miembros incluidos con fuentes | seis `data/raw/ccpc/jalisco-*.csv` + `data/raw/gis/ine-jalisco-2025-12-15.zip` |
| `sources/SOURCES.md` / `sources/sources.json` | presentes, con URL, miembro, SHA-256 y atribución |
| Docs/código | `README.md`, `docs/`, `.env.example`, `.dockerignore`, Dockerfiles, `tests/` y `.github/workflows/ci.yml` |
| Excluidos | `.env`, `.git/`, `node_modules`, cachés, `cartas`, `secret`, `credential` |

Páginas y contenido con `pypdf` sobre los archivos reales:

- `methodology.pdf`: **12** páginas; `executive.pdf`: **9** diapositivas;
  `scenario.pdf`: **4** páginas; `scenario-map.pdf`: **1** página.
- Ambos documentos institucionales contienen `M0`, 4.93, 8.90, 3.43, 8.56, 85,
  40, 70, `2025-12-15` y la advertencia de no causalidad.
- `scenario.csv`: 125 filas y valores A/B iguales al escenario persistido;
  nulos preservados. `scenario.geojson`: 125 geometrías de la referencia
  2025-12-15, EPSG:4326. Mapas A/B compuestos desde GeoServer, sin placeholder.

### Defecto de empaquetado encontrado y corregido

El primer ensayo limpio (20:53 UTC) falló al inicializar PostgreSQL:
`/docker-entrypoint-initdb.d/10-db-init.sh: Permission denied`. Causa raíz: el
ZIP escribía todos los miembros con modo `0600`, perdiendo el bit ejecutable de
`db-init.sh`. Se corrigió el escritor ZIP para preservar el modo Unix
(`external_attr`) y se añadió una prueba de regresión que exige permiso de
ejecución en el script. El ensayo limpio definitivo usó el ZIP entregado, que
contiene esta corrección.

## 7. Ensayo limpio aislado

Directorio nuevo fuera del repositorio (proyecto `participa_geo_cleanroom`,
timestamp UTC registrado en el informe T10). Se usó **solo** el ZIP técnico; no se leyeron
`/tmp/opencode/participa-geo-data-research` ni `/tmp/opencode/participa-geo-gis`.
Proyecto Compose: `participa_geo_cleanroom`, puerto `127.0.0.1:8081`, volúmenes
propios; el stack de trabajo no se borró ni se recreó.

```sh
unzip technical.zip -d ../source
sha256sum -c CHECKSUMS.sha256          # todos OK
docker compose -p participa_geo_cleanroom --env-file .env build api web
docker compose -p participa_geo_cleanroom --env-file .env up -d db geoserver
# db migrate; ingest; db load; gis import (125/750); train; model load;
# gis publish; up web
```

Resultados:

| Comprobación | Resultado |
|---|---|
| Checksums del ZIP | todos `OK` |
| `db-init.sh` extraído | modo `0755`; PostgreSQL inicializado |
| Ingesta desde fuentes empaquetadas | 750 observaciones, agregado `657245f4…3d70` |
| `db load` | 750 observaciones, 6 versiones de dataset |
| `gis import` | 125 territorios, EPSG:32613→4326, 750 correspondencias, 0 rechazadas |
| Reentrenamiento | familia **M0**, `model_run_id` `832b21e9-…`, 85 candidatos, 125 registros |
| Familia / id | iguales al paquete |
| Exclusiones (40 filas) | idénticas |
| Predicciones (125×16) | `max_abs_diff = 0.0` en A, cotas y pre-clip; máscaras nulas iguales; riesgo/elegibilidad/calidad iguales; `atol=1e-8` |
| Métricas M0/M1 2021/2024 y banda | diferencia `0.0` |
| API `/api/v1/predictions` (125) | `max_abs_diff = 0.0`; 85 elegibles; `model_run_id` igual |
| Escenario A/B creado por API en limpio | 125 filas; `max_abs_diff = 0.0`; mismo `risk_a/risk_b` |
| Readiness inicial | **200** con todos los checks |
| Readiness con GeoServer detenido | **503** `not_ready`, `gis=false`; reinicio → **200** |
| WMS GetCapabilities / GetMap | 200; PNG 512×512 de 68,640 bytes |
| WFS GetFeature | 200; 125 features |
| `/geoserver/rest/workspaces` en 8081 | **404** |

Limpieza: `docker compose -p participa_geo_cleanroom down --volumes` eliminó
**solo** los contenedores, red y volúmenes `participa_geo_cleanroom_*`
(verificado). Los volúmenes `participa-geo_pgdata` y `participa-geo_geodata` del
trabajo permanecen y el stack de trabajo sigue `ready=200`.

### Correcciones de la revisión final

La fix wave del 2026-10-27 añadió, entre otras, estas comprobaciones ejecutadas:

- identidad de observación por versión de dataset (dos versiones mismo
  municipio/año);
- `model_run_id` cambia con estados de identidad, cohortes/exclusiones y
  evidencia del candidato M1;
- cobertura empírica 2024 de la banda congelada: **71 de 75 errores (94.7 %)**,
  sin cambiar la amplitud 8.56 pp;
- `/recommendations?target_year=2027` → 200 y `2026` → 422;
- `request_id` real en el log JSON;
- reducción efectiva de escenario como rango mín–máx;
- cobertura LN 2027 etiquetada con base 2024;
- GetFeatureInfo valida capa consultada, bbox, tamaño, i/j y `info_format`;
- historia estatal paginada con total real (6);
- motivos de exclusión derivados por corte y `exclusions-by-cut.csv`;
- exportación CSV/XLSX de features, exclusiones y contribuciones M0/M1;
- arranque escalonado (`web` depende de `api` con `service_started`).

Resultado local: **214** pruebas backend, **50** Vitest, **17** E2E de producto y
**17** E2E de aceptación. No se declara CI ni AA como ejecutados/certificados.

## 8. CI

`.github/workflows/ci.yml` está configurado con acciones fijadas por SHA:

- `actions/checkout` `d23441a…` (v6.1.0)
- `astral-sh/setup-uv` `c771a70…` (v9.0.0), uv 0.9.30
- `actions/setup-node` `2499707…` (v6.5.0), Node 24.19.0

Cubre `ruff`, unitarias sin datos, contrato de salud, ESLint, typecheck, Vitest y
build con `npm ci`. **No se ejecutó en GitHub Actions** en esta sesión; no se
declara como pasado. La integración PostGIS/GeoServer, E2E y el ensayo limpio son
locales porque requieren los datos oficiales empaquetados y ~8 GB de memoria.

## 9. No ejecutado / límites de la evidencia

- GitHub Actions no se ejecutó (ver §8).
- La revisión final independiente del diff completo se ejecutó el 2026-10-27.
  Encontró 2 hallazgos críticos y 10 importantes; la ola de corrección los cerró
  y la re-revisión limitada confirmó **12/12 atendidos, sin Critical/Important
  abiertos**. Las revisiones por tarea de T1–T10 también están registradas.
- No se ejecutó un lector de pantalla real (NVDA/VoiceOver/Orca) ni una auditoría
  AA completa; sólo la inspección automatizada y de teclado descrita.
- El zoom 200% es una aproximación (Playwright no expone zoom nativo).
- No se probó un despliegue público, TLS, autenticación, multi-worker ni alta
  disponibilidad; el MVP es loopback y sin autenticación.
- No se modificaron firewall, SELinux, permisos del socket ni se instaló nada en
  el host.

## 10. Notas manuales de foco y lector (separadas)

Inspección manual realizada sobre Chromium:

- El skip link es el primer foco y se hace visible; el foco avanza por la
  navegación y activa el módulo con Enter.
- Los controles nativos (`select`, `input`) tienen `label` asociado; los botones
  iconográficos tienen `aria-label`.
- El diálogo móvil usa Radix Dialog, se cierra con Escape, devuelve el foco al
  botón que lo abrió y anuncia título/descripción.
- Los estados de carga/error usan `role="status"`/`role="alert"` y no sustituyen
  cifras por cero.
- El contenido tiene un `h1` por página, regiones con `aria-labelledby` y la
  tabla municipal como alternativa al mapa.

Pendiente manual (no automatizado): escuchar la aplicación con un lector de
pantalla real, revisar la lectura de las tablas largas y confirmar la redacción
final. **No se afirma conformidad AA.**

## 11. Conclusión técnica

La aceptación técnica local pasa: backend 214, Vitest 50, Playwright 17+17,
GIS/readiness/seguridad, documentos 12/9, ZIP `complete=true` con fuentes y
checksums, y reproducción limpia con diferencia 0.0 (`atol=1e-8`). La revisión
final independiente quedó cerrada (12/12 hallazgos atendidos). Quedan como
condiciones humanas la revisión de redacción, las cartas y el envío; la
redistribución de fuentes fue confirmada por el usuario para este paquete con
`--confirm-source-license` y atribución/checksums.

## 12. Aceptación nacional Task 11 — 2026-10-28

### CI y pruebas

- `.github/workflows/ci.yml` configura Ruff, todas las pruebas unitarias,
  contratos nacionales de distrito/health/OpenAPI sin DB, ESLint, TypeScript,
  Vitest y build. GitHub Actions **no se ejecutó**; la configuración no se
  presenta como resultado de un run remoto.
- Suite backend completa, contra el stack real: **243 passed, 76 skipped, 1
  warning** (`StarletteDeprecationWarning`, `httpx`/TestClient), 243.13 s.
  Los skips de Jalisco que ahora están marcados en `tests/conftest.py` reemplazan
  fixtures obsoletos de 125 municipios/filas; las rutas nacionales equivalentes
  sí se ejecutan. Dos skips adicionales conservan razón: falta el GeoJSON MVP
  para scenario delivery/GeoJSON histórico.
- Suite Playwright real: **16 passed, 2 skipped** (1.6 min). Incluye cobertura
  nacional, resumen de 32 entidades, `page_size=500`, perfil DERFE2023 observado
  2024, distrito predicción/escenario 409, rechazo de WFS nacional completo,
  cambio de nivel y todas las pruebas de teclado, axe y reflow. Los dos journeys
  Jalisco 125-row de `full-journey.spec.ts` están marcados `test.skip` con
  reemplazos explícitos en `national-acceptance.spec.ts` y contratos nacionales.
- Web Docker test (sin source volume): ESLint y typecheck pasaron; Vitest **10
  archivos / 67 tests** pasaron; build de producción pasó. Se conserva aviso
  informativo de MapLibre >500 kB; Vitest muestra requests MSW no manejadas en
  casos que siguen pasando.
- Ruff `check .`: pasó. Contratos seleccionados de CI sin DB: health **5 passed**,
  lectura nacional **3 passed / 19 deselected**, escenarios/nivel **5 passed / 8
  deselected**. `docker compose config --quiet`: pasó.
- Los checks de accesibilidad no son certificación WCAG/AA.

### Rendimiento medido, API `127.0.0.1:8081`

Primera solicitud medida y luego 30 solicitudes calientes (WMS 10):

| Operación | Primera | p95 caliente | Umbral | Resultado |
|---|---:|---:|---:|---|
| WMS GetMap 1200×900 | 0.9581 s | 0.9504 s | frío ≤5 / caliente ≤2.5 s | pasa |
| WFS estado 14, `count=1000` | 0.3094 s | 0.3428 s | ≤3 s | pasa; ≤1,000 features |
| API municipio state14, page500 | 0.0275 s | 0.0245 s | ≤500 ms | pasa |
| Resumen 32 entidades | 0.0306 s | 0.0239 s | ≤1 s | pasa |

La optimización en `Repository.get_participation_summary` reemplaza la selección
correlacionada por fila por una selección `DISTINCT ON` del último dataset por
entidad. Las pruebas automáticas de los umbrales están en
`tests/integration/national/test_performance.py` (**4 passed**). Mediciones
locales, no garantías generales.

### ZIP nacional

- CLI `deliver --output-dir dist/national --confirm-source-license` y
  `verify-delivery` completaron con `complete: true`, 311 miembros verificados,
  `scenario_required: false`, sources mode `confirm`.
- `dist/national/technical.zip`: el tamaño/SHA-256 exactos del build final están
  en el `DELIVERY.json` contiguo y en el informe Task 11. Incluye 6 archivos
  CCPC y 32 MGS ZIP; el manifiesto/checksums reporta atribución y hash. La
  verificación de contenido confirmó ausencia de `.env`, `.git`,
  cartas/credenciales o datos personales. Distrito es observado 2024; no hay
  artefacto de predicción distrital.

### Ensayo cleanroom: bloqueado por insumos fuera del ZIP

Se extrajo el ZIP de aceptación al directorio nuevo
`/tmp/opencode/participa-geo-national-cleanroom-20261028T190000Z`, con proyecto
`participa_geo_national_cleanroom`, volúmenes propios y web `8082`. Los 312
checksums de `CHECKSUMS.sha256` dieron `OK`; las imágenes API/web se construyeron
desde el código extraído. DB subió y Alembic migró de cero hasta `0013`.

- `ingest-national` leyó los 6 CCPC (192 CSV), procesó y cargó en PostGIS
  **54,872,712 facts**, con 14,779 observaciones municipales (2,477 en 2024),
  300 distritos versionados y 44,154 `DEF` vacíos.
- `db load --processed-dir .../national-cleanroom` falló con
  `FileNotFoundError: .../provenance.json`: ese comando consume el formato legado
  MVP; `ingest-national` es el cargador nacional (incluye carga PostGIS).
- `district rebuild` falló antes de procesar con
  `ContinuityError: official historical CSV not found:
  /workspace/data/raw/continuity/official-section-history.csv`. El ZIP no contiene
  dicho CSV, el ACCDB INE ni `district-headquarters.txt`.
- `gis import-national` confirmó la falta de `district-headquarters.txt`:
  `official district-headquarters catalogue must contain 300 unique labels,
  found 0`. En consecuencia, no fue posible entrenar/reconstruir el bundle en
  cleanroom; el intento de train anterior al import terminó con
  `incomplete MGS municipality reference: 0/2477 municipalities across 0/32 states`.
- Por tanto no se afirma readiness, GIS publish, WMS/WFS, API nacional ni
  equivalencia `atol=1e-8` en cleanroom. El ZIP contiene datos procesados y el
  bundle publicado usados por el producto, pero no todos los insumos fuente
  intermedios necesarios para recalcular la continuidad/catalogación desde cero.

La limpieza debe limitarse a `docker compose -p
participa_geo_national_cleanroom ... down --volumes`; no se tocó ni se eliminaron
volúmenes del proyecto nacional o MVP. La reproducción integral requiere que el
responsable de fuentes decida si añadir y atribuir los insumos de continuidad al
paquete o aprobar un contrato de rebuild que consuma evidencia derivada
versionada. Hasta entonces: **DONE_WITH_CONCERNS**.
