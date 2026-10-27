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
| Node (web, T7) | 24 LTS (referencia) |

Los digests exactos están en `docs/architecture/dependencies.md`.

### Puesta en marcha

```sh
# 1. Crear el fichero de entorno local (ignorado por Git) y fijar secretos reales.
cp .env.example .env
#    editar .env: cambiar todos los valores "change-me-*"

# 2. Construir la imagen de la API (descarga imagen base uv y wheels de PyPI).
docker compose build api

# 3. Levantar la API (sólo publica 127.0.0.1:8000).
docker compose up -d api

# 4. Comprobar.
curl -i http://127.0.0.1:8000/api/v1/health/live
curl -i http://127.0.0.1:8000/api/v1/health/ready   # 503 hasta T2–T5
```

`db` y `geoserver` no publican puertos de host: sólo son alcanzables dentro de la
red `internal` de Compose. La API publica únicamente `127.0.0.1:8000`.

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

## Estructura

```text
apps/api/participa_geo/   # API FastAPI y CLI
infrastructure/docker/    # Dockerfile de la API y db-init.sh
tests/                    # unit, contract, integration
docs/api/                 # contrato HTTP
docs/architecture/        # dependencias e imágenes
compose.yaml
pyproject.toml / uv.lock
.env.example
```

## Pendiente (tareas siguientes)

- T4: modelo Ridge interpretable y evaluación temporal.
- T5: rutas de lectura y gateway GIS; exportación OpenAPI.
- T6: escenarios y recomendaciones.
- T7–T9: interfaz web, mapas comparativos y entregables institucionales.
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
