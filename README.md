# PARTICIPA-GEO — MVP

Análisis municipal de participación electoral (Jalisco, 2009–2027), con
referencia cartográfica INE 2025, modelo interpretable, escenarios hipotéticos y
entregables institucionales. Piloto municipal; sin autenticación y de uso local.

## Entorno reproducible

Todo el software de aplicación corre en contenedores; no se instala nada en el
host. El proyecto usa un único `pyproject.toml`/`uv.lock` para Python y un único
`compose.yaml`.

### Versiones fijadas

| Componente | Versión |
|---|---|
| Docker Engine | 29.9.2 |
| Docker Compose | 5.6.1 |
| Python (imagen) | 3.12 (uv `python3.12-bookworm-slim`) |
| PostgreSQL + PostGIS | `postgis/postgis:17-3.6` (digest fijado) |
| GeoServer | `docker.osgeo.org/geoserver:2.28.6` (digest fijado) |
| Node (web, T7) | 24 LTS (`node:24-bookworm-slim`, digest fijado) |
| nginx (web, T7) | 1.29 (`nginx:1.29-bookworm`, digest fijado) |

Los digests exactos están en `docs/architecture/dependencies.md`.

### Puesta en marcha

```sh
# 1. Crear el fichero de entorno local (ignorado por Git) y fijar secretos reales.
cp .env.example .env
#    editar .env: cambiar todos los valores "change-me-*"

# 2. Construir las imágenes (API Python y web Node/nginx).
docker compose build api web

# 3. Levantar el stack. Sólo la web publica un puerto de host.
docker compose up -d db geoserver api web

# 4. Comprobar a través del proxy del mismo origen.
curl -i http://127.0.0.1:8080/api/v1/health/live
curl -i http://127.0.0.1:8080/api/v1/health/ready
# Interfaz: http://127.0.0.1:8080/territory?year=2024
```

`db` y `geoserver` no publican puertos de host: sólo son alcanzables dentro de la
red `internal` de Compose. La API tampoco publica un puerto de host; nginx en
`web` reenvía `/api/` a `api:8000`. El navegador nunca habla con GeoServer.

### Comandos probados (T1)

```sh
docker compose config --quiet
docker compose run --rm --no-deps api pytest -q                          # 14 passed
docker compose run --rm --no-deps api python -m participa_geo.cli --help
```

Resultado registrado: `14 passed` (unit/contract/integration), `docker compose
config --quiet` sale 0, y la API responde `200` en `/health/live`, `503
problem+json` en `/health/ready` y `404 problem+json` en rutas desconocidas.

### Comandos probados (T2/T3)

```sh
# Ingestión CCPC (T2): 750 observaciones municipales.
docker compose run --rm --no-deps api python -m participa_geo.cli ingest \
  --source-dir data/raw/ccpc --output-dir data/processed

# PostGIS (T3): migrar, cargar observaciones e importar geometría de referencia.
docker compose up -d db geoserver
docker compose run --rm api python -m participa_geo.cli db migrate
docker compose run --rm api python -m participa_geo.cli db load --processed-dir data/processed
docker compose run --rm api python -m participa_geo.cli gis import \
  --archive data/raw/gis/ine-jalisco-2025-12-15.zip

# Publicar y verificar WMS/WFS de sólo lectura en GeoServer.
docker compose run --rm api python -m participa_geo.cli gis publish
docker compose run --rm api python -m participa_geo.cli gis verify

# Tests de integración GIS reales.
docker compose run --rm api pytest tests/integration/test_postgis.py \
  tests/integration/test_geography.py tests/integration/test_geoserver.py -q
```

Los comandos `db load`, `gis import` y `gis publish` son idempotentes (los
identificadores `uuid5` y los `ON CONFLICT` evitan duplicados).

### Comandos probados (T7, web)

```sh
docker compose run --rm --no-deps --build web-test npm run test -- --run
docker compose --profile tools run --rm --no-deps web-e2e npx playwright test
```

Vitest cubre filtros de URL, shell, foco móvil, datos ausentes, respuestas
tardías y alternativa tabular. Playwright corre contra la API real a través de
`http://web:80`; no usa MSW. Los detalles y contrastes están en
`docs/design-system/README.md`.

## Comandos probados (T9, entregables)

```sh
# Requiere un escenario persistido (UUID de /api/v1/scenarios) y el stack GIS activo.
# Elija un modo de fuentes; no hay modo implícito.
docker compose run --rm api python -m participa_geo.cli deliver \
  --scenario-id <UUID> --output-dir dist/hackathon --team-slug participa-geo \
  --confirm-source-license   # incluye los CSV/ZIP originales sólo tras confirmar
# o, sin originales (URL/checksums):
docker compose run --rm api python -m participa_geo.cli deliver \
  --scenario-id <UUID> --output-dir dist/hackathon --team-slug participa-geo \
  --skip-sources
docker compose run --rm api python -m participa_geo.cli verify-delivery \
  --archive dist/hackathon/technical.zip
```

`--confirm-source-license` es una decisión humana sobre la redistribución de
INE/cartografía; si no se confirma, `--skip-sources` genera un paquete con
`sources/SOURCES.md` y `sources/sources.json` (URL y SHA-256) sin originales.
Omitir ambas opciones hace que `deliver` falle con código distinto de cero.
`verify-delivery` falla si el paquete está incompleto; `--allow-incomplete` es
sólo para diagnóstico.

`deliver` escribe el reporte metodológico (12 páginas), la presentación
ejecutiva (9 diapositivas), CSV/GeoJSON/PDF del escenario, mapas A/B y el
`technical.zip` con manifiesto/checksums. También publica los tres documentos
institucionales en `data/processed/reports/institutional`, que es lo único que
la API sirve para `methodology_pdf`, `executive_pdf` y `technical_zip`; si no se
han generado, `POST /reports` devuelve `409 institutional_package_not_generated`
(sin cola ni estado pendiente).

El ZIP incluye diccionarios, agregados/artefactos del modelo, código/docs,
`docs/api/openapi.json`, reportes/mapas condicionados al escenario y checksums.
Los seis CSV CCPC y el ZIP cartográfico original sólo se añaden con
`--confirm-source-license`; en `--skip-sources` se sustituyen por
`sources/SOURCES.md` y `sources/sources.json` con URL y checksums. Excluye
`.git`, `node_modules`, cachés, `.env`, cartas firmadas, contactos y datos
personales. Las condiciones de redistribución se documentan en
`docs/hackathon/source-licenses.md` y requieren confirmación humana antes de una
publicación abierta.

## Estructura

```text
apps/api/participa_geo/   # API FastAPI y CLI
apps/web/                 # React/Vite/TS, MapLibre y pruebas web
infrastructure/docker/    # Dockerfiles de API/web, nginx y db-init.sh
tests/                    # unit, contract, integration
docs/api/                 # contrato HTTP
docs/architecture/        # dependencias e imágenes
docs/design-system/       # tokens, shell y verificaciones de UI
compose.yaml
pyproject.toml / uv.lock
apps/web/package-lock.json
.env.example
```

## Pendiente (tareas siguientes)

- T10: CI, ensayo limpio y aceptación final.

Mientras no se carguen datos, migraciones, modelo y capas GIS, `/health/ready`
devuelve `503` (por diseño); `live` no depende de GIS.

## Seguridad y límites

- Sin secretos en Git: `.env` está ignorado y `.env.example` sólo tiene
  marcadores `change-me-*`. Logs JSON con `request_id`, sin credenciales.
- Cuerpos JSON limitados a 32 KiB (`413`). Errores `application/problem+json`.
- Roles de base de datos separados: `migrator`, `writer`, `api`, `gis_reader`
  (la API nunca usa `migrator`).
- Sólo loopback. No se modifica firewall/SELinux ni se publica el socket Docker.
