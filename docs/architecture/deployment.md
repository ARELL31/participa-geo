# Despliegue local y operación

Estado: **despliegue local nacional de loopback, sin autenticación ni exposición
pública**. El producto cubre municipios nacionales y observación distrital 2024;
no existe predicción distrital 2027. No se abre firewall, no se publica el
socket Docker ni se configura TLS o un dominio público.

## 1. Arquitectura desplegada

```text
navegador
   │  http://127.0.0.1:8080 (loopback)
   ▼
web (nginx) ── /api/* ──► api (FastAPI, :8000, sólo red interna)
   │                         │
   │                         ├─► db (PostgreSQL 17 + PostGIS, :5432, sólo red interna)
   │                         └─► geoserver (:8080, sólo red interna)
   └─ estáticos Vite/React
```

- Sólo `web` publica un puerto de host, y lo hace en `127.0.0.1`.
- `db` y `geoserver` no publican puertos. `/geoserver/` se bloquea con `404` en
  nginx; la administración de GeoServer sólo es alcanzable desde la red interna.
- La API no tiene autenticación ni perfiles: es un piloto de uso local. Cualquier
  persona con acceso al host puede usar la aplicación.
- Los datos son agregados municipales. No hay datos personales, listas nominales
  ni identificadores individuales en la API, la base analítica, los reportes o el
  ZIP técnico.

## 2. Requisitos medidos

| Recurso | Observado / mínimo |
|---|---|
| Docker Engine / Compose | 29.9.2 / 5.6.1 (probados) |
| Memoria del host | 7.7 GiB; stack ocioso ≈ 1.26 GiB (api 185 MiB, GeoServer 958 MiB, db 103 MiB, web 10 MiB) |
| Paquete nacional confirmado | ≈439 MiB comprimidos; seis CCPC y 32 MGS ZIP |
| CPU | no se fija límite; el entrenamiento y los PDFs son las cargas más largas |
| Navegador | Chromium reciente (Playwright 1.64.1 para la suite) |

Los límites son observaciones, no garantías. En un host de 8 GB se recomienda un
solo worker de Playwright y no ejecutar el stack limpio y el de trabajo a la vez.

## 3. Instalación desde el ZIP técnico

El paquete `--confirm-source-license` incluye `.env.example`, `.dockerignore`,
los Dockerfiles, el código, los tests, los artefactos del modelo y las fuentes
originales con atribución/checksums. No incluye `.env`, `.git`, `node_modules`,
cartas ni secretos.

```sh
mkdir -p /tmp/opencode/participa-geo-install
cd /tmp/opencode/participa-geo-install
unzip /ruta/technical.zip
sha256sum -c CHECKSUMS.sha256

cp .env.example .env
# Generar secretos locales, nunca reutilizar los marcadores change-me-*:
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
sed -i "s/^DB_MIGRATOR_PASSWORD=.*/DB_MIGRATOR_PASSWORD=$(openssl rand -hex 24)/" .env
sed -i "s/^DB_WRITER_PASSWORD=.*/DB_WRITER_PASSWORD=$(openssl rand -hex 24)/" .env
sed -i "s/^DB_API_PASSWORD=.*/DB_API_PASSWORD=$(openssl rand -hex 24)/" .env
sed -i "s/^DB_GIS_READER_PASSWORD=.*/DB_GIS_READER_PASSWORD=$(openssl rand -hex 24)/" .env
sed -i "s/^GIS_ADMIN_PASSWORD=.*/GIS_ADMIN_PASSWORD=$(openssl rand -hex 24)/" .env
chmod 600 .env
```

Los seis secretos deben ser aleatorios y distintos. `.env` está en
`.gitignore` y nunca entra en el ZIP; `.env.example` sólo contiene marcadores.

### Puertos y proyectos aislados

`WEB_PORT` cambia únicamente el puerto de loopback. Para un ensayo limpio se usa
otro nombre de proyecto y otro puerto:

```sh
docker compose -p participa_geo_cleanroom --env-file .env up -d db geoserver
# .env: WEB_PORT=8081
```

Los volúmenes quedan ligados al nombre de proyecto
(`participa_geo_cleanroom_pgdata`, `participa_geo_cleanroom_geodata`). Nunca
ejecute `down -v` sobre el proyecto de trabajo.

## 4. Construcción y arranque

```sh
docker compose config --quiet
docker compose build api web
docker compose up -d db geoserver
docker compose up -d api
# db migrate; ingest; db load; gis import; train; model load; gis publish
docker compose up -d web
docker compose ps
curl -i http://127.0.0.1:8080/api/v1/health/live
curl -i http://127.0.0.1:8080/api/v1/health/ready
```

Orden de dependencias: `api` espera `db` y `geoserver`; `web` espera `api` con
`condition: service_started`, no con readiness. Esto permite que la web arranque
mientras se ejecutan migraciones, ingesta, modelo y GIS; la interfaz muestra
estados de carga/vacío/no disponible y nunca cifras ficticias. `api` tiene
healthcheck contra `/api/v1/health/ready`; `web` contra `/healthz`; `db` y la
imagen de GeoServer traen sus propios healthchecks. `docker compose up` sin datos
deja `ready=503` (por diseño). La secuencia escalonada completa está en README y
en `verification-results.md`.

### Volúmenes y respaldo

| Volumen | Contenido | Respaldo |
|---|---|---|
| `participa-geo_pgdata` | PostgreSQL/PostGIS, escenarios persistidos | `pg_dump` o copia del volumen con el stack detenido |
| `participa-geo_geodata` | datos y estilos de GeoServer | recopilable con `gis import`/`gis publish`; no es la fuente de verdad |

Los originales INE y los artefactos procesados viven en `data/` (ignorado por
Git). El ZIP técnico es la copia reproducible; no depende de `/tmp/opencode`.

### Logs

Todos los servicios usan el driver `json-file` con rotación `max-size=10m` y
`max-file=3`. Para revisar:

```sh
docker compose logs --tail=100 api
docker compose logs -f geoserver
```

No hay logs con credenciales; los errores de API usan `application/problem+json`
y no devuelven rutas internas.

## 5. Migración, ingestión, modelo y GIS

```sh
# 1. Esquema (rol migrator).
docker compose run --rm api python -m participa_geo.cli db migrate

# 2. Agregados CCPC desde los seis CSV oficiales (verifica SHA-256).
docker compose run --rm api python -m participa_geo.cli ingest \
  --source-dir data/raw/ccpc --output-dir data/processed

# 3. Observaciones y versiones de dataset en PostGIS.
docker compose run --rm api python -m participa_geo.cli db load \
  --processed-dir data/processed

# 4. Geometría de referencia INE 2025 (rol writer); requiere el catálogo
#    municipal ya cargado para verificar las 125 identidades.
docker compose run --rm api python -m participa_geo.cli gis import \
  --archive data/raw/gis/ine-jalisco-2025-12-15.zip

# 5. Modelo M0/M1 con validación temporal 2021 y prueba 2024.
docker compose run --rm api python -m participa_geo.cli train \
  --processed-dir data/processed --output-dir data/processed/model

# 6. Cargar modelo y predicciones 2027 (rol writer).
docker compose run --rm api python -m participa_geo.cli model load \
  --bundle-dir data/processed/model

# 7. Publicar capas de sólo lectura y endurecer WFS (Básico, sin Transaction).
docker compose run --rm api python -m participa_geo.cli gis publish
docker compose run --rm api python -m participa_geo.cli gis verify
```

`ingest`, `db load`, `gis import` y `gis publish` son idempotentes. `train` es
determinista y escribe `model_run_id` como `uuid5` del contenido. El esquema
temporal no cambia: 2015/2018 ajuste, 2021 validación, 2024 prueba y 2027
pronóstico; M0 fue seleccionado porque M1 no redujo el MAE de validación.

## 6. Reportes y entrega

```sh
# Un escenario persistido (la UUID sale de POST/GET /api/v1/scenarios).
docker compose run --rm api python -m participa_geo.cli deliver \
  --scenario-id <UUID> --output-dir dist/hackathon --team-slug participa-geo \
  --confirm-source-license

docker compose run --rm api python -m participa_geo.cli verify-delivery \
  --archive dist/hackathon/technical.zip
```

- `--confirm-source-license` incluye los seis CSV y el ZIP cartográfico original
  con atribución/checksums. Es una decisión humana sobre la redistribución.
- `--skip-sources` genera `sources/SOURCES.md` y `sources/sources.json` con URL y
  SHA-256, sin originales. Omitir ambas opciones falla con código 2.
- `deliver` necesita GeoServer: los mapas A/B no se sustituyen por un placeholder.
- El ZIP excluye `.env`, `.git`, `node_modules`, cachés, cartas y secretos, y
  contiene `.env.example`, Dockerfiles, tests, CI, artefactos y reportes.

## 7. Comprobaciones de operación

```sh
# Salud y degradación (detener GeoServer debe producir 503 con gis=false).
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/api/v1/health/ready
docker compose stop geoserver
sleep 4
curl -s http://127.0.0.1:8080/api/v1/health/ready
docker compose start geoserver

# Gateway WMS/WFS de sólo lectura a través del mismo origen.
curl -s -o /dev/null -w 'wms:%{http_code}\n' \
  'http://127.0.0.1:8080/api/v1/gis/wms?service=WMS&version=1.3.0&request=GetCapabilities'
curl -s -o /dev/null -w 'wfs:%{http_code}\n' \
  'http://127.0.0.1:8080/api/v1/gis/wfs?service=WFS&version=2.0.0&request=GetCapabilities'

# La administración no está expuesta en el origen web.
curl -s -o /dev/null -w 'admin:%{http_code}\n' http://127.0.0.1:8080/geoserver/rest/workspaces
```

## 8. Apagado

```sh
docker compose stop
# Sólo para el proyecto aislado que usted creó:
# docker compose -p participa_geo_cleanroom down --volumes
```

No hay `down -v` en las instrucciones normales: borra escenarios y datos. No se
publica el puerto 8080 fuera de loopback, no se modifica firewall/SELinux y no se
expone el socket de Docker.

## 9. Limitaciones de despliegue

- Sin autenticación, autorización ni multiusuario; no es un servicio público.
- Un solo worker de API y límites de tasa/exportación en memoria; no son
  distribuidos ni sobreviven a un reinicio.
- GeoServer es obligatorio para mapa y `deliver`; la degradación es explícita
  (`503`/error visible y alternativa tabular), no un mapa falso.
- El modelo nacional incluye 2,477 municipios (1,623 elegibles; 854 insuficientes)
  para 2027. Los 300 distritos sólo muestran observado 2024/DERFE2023 con
  cobertura explícita; no se predice ni se crean escenarios distritales.
- WMS nacional y WFS acotado por entidad/bbox (máximo 1,000 elementos); no se
  ofrece descarga WFS nacional completa.

## 10. Rendimiento y aceptación nacional (Task 11)

Medición local del stack nacional real, desde loopback `127.0.0.1:8081`; GetMap
de 1200×900, una primera llamada y 30 llamadas calientes para API/WFS (10 para
WMS). Resultados en la corrida del 2026-10-28:

| Operación | Primera (s) | p95 caliente (s) | Límite | Resultado |
|---|---:|---:|---:|---|
| WMS nacional GetMap 1200×900 | 0.9581 | 0.9504* | 5.0 frío / 2.5 caliente | Pasa |
| WFS estado 14, count 1,000 | 0.3094 | 0.3428 | 3.0 | Pasa |
| API municipios entidad 14, page 500 | 0.0275 | 0.0245 | 0.500 | Pasa |
| Resumen nacional de 32 entidades | 0.0306 | 0.0239 | 1.0 | Pasa |

*WMS caliente medido con 10 repeticiones. Prueba automatizada reproducible:
`tests/integration/national/test_performance.py`; suite Playwright de aceptación:
`tests/e2e/national-acceptance.spec.ts`. Las cifras son mediciones de este
entorno, no garantías de producción.

La consulta de resumen se optimizó para elegir una vez el dataset municipal más
reciente por entidad, en lugar de ejecutar una subconsulta correlacionada por
fila observada.

### Ensayo limpio nacional

El paquete final se extrae a un directorio nuevo bajo
`/tmp/opencode/participa-geo-national-cleanroom-<timestamp>`. El proyecto Compose
se llama `participa_geo_national_cleanroom` y el puerto web es 8082; usa volúmenes
propios y nunca reutiliza ni borra volúmenes del proyecto nacional o del MVP.
Se valida `CHECKSUMS.sha256`, readiness, API, WMS/WFS y la prohibición de
predicción/escenario distrital; al finalizar se elimina sólo el proyecto
cleanroom. El detalle y cualquier limitación verificable se registra en
`docs/hackathon/verification-results.md`.

El ZIP confirmado incluye 6 CCPC, 32 MGS y los tres insumos de continuidad/catálogo
con atribución y hashes. La prueba cleanroom más reciente, su alcance y cualquier
limitación se documentan en `docs/hackathon/verification-results.md`; no debe
inferirse aceptación completa únicamente de que el ZIP verifique sus checksums.
