# Dependencias, imágenes y descargas

Todo el software de aplicación se ejecuta dentro de contenedores; no se instala
nada en el host. Las versiones se fijan por digest de imagen y por `uv.lock`.

## Imágenes base (fijadas por digest, amd64)

| Imagen | Referencia fijada | Digest del manifest amd64 |
|---|---|---|
| Python 3.12 + uv | `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` | `sha256:5d275ca5f0da33c3368ac8fbb85fafabad023b3b8a7cff39a94ac0baecfd9a50` |
| PostgreSQL 17 + PostGIS | `postgis/postgis:17-3.6` | `sha256:5d4c5c5d10b415bec52b0b9cea1ae93ace3a451ff10ab8f8974988e336274452` |
| GeoServer 2.28.6 | `docker.osgeo.org/geoserver:2.28.6` | `sha256:9f3b93ce6bfeff0f560a3867eeb76d5b5b46afacde8712ad4a793c27fd773a85` |
| Node 24 LTS (T7, web) | `node:24-bookworm-slim` | `sha256:55fb5f5a527ea2c5c4a95f963e48ef90aa38c7b346054fdc8ee9957a2b55d205` |
| nginx 1.29 (T7, web runtime) | `nginx:1.29-bookworm` | `sha256:8adbdcb969e2676478ee2c7ad333956f0c8e0e4c5a7463f4611d7a2e7a7ff5dc` |

Se verificó la existencia de `postgis/postgis:17-3.6` y
`docker.osgeo.org/geoserver:2.28.6` en sus registros oficiales antes de fijar el
digest. No se usa `latest`; no se sustituye un tag por otro sin reportarlo.

Los digests de Node 24 y nginx se verificaron de nuevo en T7 con
`docker image inspect` (26 de octubre de 2026). El tag móvil
`node:24-bookworm-slim` ya resolvía al digest `55fb5f…`, no al `2dd9a4…`
anotado en T1; se fijó el digest vigente y se retiró el anterior. La imagen web
de ejecución es `nginx:1.29-bookworm` por digest, no `latest`.
`docker.osgeo.org/geoserver` es el registro oficial del proyecto
[geoserver/docker](https://github.com/geoserver/docker).

## Dependencias Python

El entorno se gestiona con `uv`. El lock (`uv.lock`, formato v1) fija la versión
exacta y el hash de cada distribución; se genera con `uv lock` y se instala con
`uv sync --frozen --all-groups --no-install-project` (el proyecto no se instala
como distribución: el contenedor expone el código con `PYTHONPATH=/workspace/apps/api`).

Dependencias directas de ejecución (licencias de referencia, revisadas antes de
redistribución en T9):

| Paquete | Uso | Licencia |
|---|---|---|
| fastapi | Framework HTTP | MIT |
| pydantic / pydantic-settings | Schemas y configuración | MIT |
| uvicorn | Servidor ASGI | BSD-3-Clause |
| sqlalchemy | ORM | MIT |
| alembic | Migraciones | MIT |
| psycopg (binary) | Driver PostgreSQL (psycopg3) | LGPL-3.0 |
| pandas | Agregados y tablas | BSD-3-Clause |
| pyarrow | Parquet | Apache-2.0 |
| numpy | Cómputo numérico | BSD-3-Clause |
| scikit-learn | Modelo Ridge/scaler | BSD-3-Clause |
| geopandas | Geometrías | BSD-3-Clause |
| shapely | Operaciones geométricas | BSD-3-Clause |
| pyproj | Transformación de CRS | MIT |
| reportlab | PDF | BSD-3-Clause |
| openpyxl | XLSX | MIT |
| matplotlib | Gráficos | PSF/BSD-like |
| pillow | Imágenes | MIT-CMU |

Dependencias de desarrollo/pruebas (`[dependency-groups].dev`): `pytest` (MIT),
`httpx` (BSD-3-Clause), `pyyaml` (MIT), `ruff` (MIT), `mypy` (MIT), `pypdf`
(BSD-3-Clause).

## Descargas previstas

- Al construir la imagen `api`: imagen base `ghcr.io/astral-sh/uv` (~250 MB) y
  wheels de PyPI de las dependencias anteriores (numpy, pandas, scipy,
  scikit-learn, pyarrow, geopandas/pyogrio/proj, matplotlib, reportlab…).
- Al levantar el stack: `postgis/postgis:17-3.6` (~450 MB) y
  `docker.osgeo.org/geoserver:2.28.6` (~1 GB).
- Node 24 y nginx 1.29 se descargaron en T7 al añadir el servicio web; las
dependencias npm se fijan en `apps/web/package-lock.json` (instaladas con
`npm ci` dentro de Docker).

La ejecución de tests en T1 no levanta `db` ni `geoserver`; sus imágenes sólo
quedan referenciadas por digest en `compose.yaml`.
