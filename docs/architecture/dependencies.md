# Dependencias, imágenes y descargas

Todo el software de aplicación se ejecuta dentro de contenedores; no se instala
nada en el host. Las versiones se fijan por digest de imagen y por `uv.lock`.

## Imágenes base (fijadas por digest, amd64)

| Imagen | Referencia fijada | Digest del manifest amd64 |
|---|---|---|
| Python 3.12 + uv | `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` | `sha256:5d275ca5f0da33c3368ac8fbb85fafabad023b3b8a7cff39a94ac0baecfd9a50` |
| PostgreSQL 17 + PostGIS | `postgis/postgis:17-3.6` | `sha256:5d4c5c5d10b415bec52b0b9cea1ae93ace3a451ff10ab8f8974988e336274452` |
| GeoServer 2.28.6 | `docker.osgeo.org/geoserver:2.28.6` | `sha256:9f3b93ce6bfeff0f560a3867eeb76d5b5b46afacde8712ad4a793c27fd773a85` |
| Node 24 LTS (T7, web) | `node:24-bookworm-slim` | `sha256:2dd9a4f758e173b65fee15388f7706af6fb01ef50cf7a2c0538711d67a6981ae` |

Se verificó la existencia de `postgis/postgis:17-3.6` y
`docker.osgeo.org/geoserver:2.28.6` en sus registros oficiales antes de fijar el
digest. No se usa `latest`; no se sustituye un tag por otro sin reportarlo.
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
- Node 24 se descargará en T7 al añadir el servicio web.

La ejecución de tests en T1 no levanta `db` ni `geoserver`; sus imágenes sólo
quedan referenciadas por digest en `compose.yaml`.
