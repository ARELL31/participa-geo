# PARTICIPA-GEO Nacional

Plataforma local de inteligencia territorial con cobertura de **32 entidades,
2,477 municipios y 300 distritos federales**. Usa seis cortes CCPC del INE
(2009–2024), geometría MGS del plan DERFE2023, API FastAPI, PostGIS/GeoServer y
una interfaz React.

## Alcance y límites del producto

- **Municipios:** modelo nacional M0/M1 para la estimación intermedia 2027;
  2,477 territorios, con elegibilidad y datos insuficientes diferenciados.
- **Distritos:** perfil observado 2024 bajo DERFE2023 y cobertura explícita.
  No existe modelo, predicción, banda, semáforo predictivo ni escenario distrital
  2027. Las rutas de predicción/escenario distrital responden 409.
- El mapa nacional usa WMS raster. WFS sólo está disponible acotado por entidad
  o bbox y limita cada consulta a 1,000 elementos; no descargar 2,477 geometrías
  al navegador.
- La relación municipio–distrito es N:M (2,581 pares; 72 municipios partidos).
  No se agregan predicciones municipales para producir cifras distritales.
- Aplicación local de loopback, sin autenticación ni exposición pública. La
  verificación automatizada de accesibilidad no es certificación AA.

## Requisitos y arranque

Se requiere Docker Engine/Compose. No es necesario instalar dependencias de
Python o Node en el host. `data/` contiene fuentes y artefactos nacionales
ignorados por Git; para una instalación desde ZIP consulte
[`docs/architecture/deployment.md`](docs/architecture/deployment.md).

```sh
cp .env.example .env
# Sustituir cada valor change-me-* por un secreto aleatorio distinto.
chmod 600 .env

sg docker -c 'docker compose config --quiet'
sg docker -c 'docker compose up -d db geoserver'
sg docker -c 'docker compose up -d api'
sg docker -c 'docker compose exec -T api python -m participa_geo.cli db migrate'
sg docker -c 'docker compose up -d web'
```

La aplicación responde en `http://127.0.0.1:${WEB_PORT:-8080}`. En el worktree
de aceptación, `WEB_PORT=8081`. GeoServer y PostGIS no publican puertos de host.
La readiness `/api/v1/health/ready` sólo es 200 cuando DB, migraciones, datos,
modelo y GIS están disponibles.

## Pipeline nacional reproducible

Los comandos se ejecutan en el servicio API; requieren los insumos nacionales
con atribución y checksums validados. Ejecute la secuencia en un entorno limpio
con proyecto Compose propio, no sobre volúmenes con otros datos.

```sh
sg docker -c 'docker compose exec -T api python -m participa_geo.cli ingest-national \
  --source-dir data/raw/ccpc-national \
  --output-dir data/processed/national'
sg docker -c 'docker compose exec -T api python -m participa_geo.cli gis import-national \
  --archive-dir data/raw/gis/national'
sg docker -c 'docker compose exec -T api python -m participa_geo.cli train-national-municipal \
  --processed-dir data/processed/national \
  --output-dir data/processed/national/model'
sg docker -c 'docker compose exec -T api python -m participa_geo.cli model load-national \
  --bundle-dir data/processed/national/model'
sg docker -c 'docker compose exec -T api python -m participa_geo.cli gis publish-national'
sg docker -c 'docker compose exec -T api python -m participa_geo.cli gis verify-national'
```

Continuity/reconstruction uses the separately validated INE section-history
inputs described in `docs/methodology/national-district-reconstruction.md`.
`ingest-national` streams and loads all 54,872,712 section facts into PostGIS;
the legacy `db load` command consumes the MVP `provenance.json` format and is
not the loader for national ingestion.
Current product data deliberately expose district observation 2024 only because
the national historical continuity gate did not meet 98% coverage.

## Verification

```sh
sg docker -c 'docker compose exec -T api ruff check .'
sg docker -c 'docker compose exec -T api python -m pytest -q'
sg docker -c 'docker compose run --rm --no-deps --build web-test sh -lc \
  "npm run lint && npm run typecheck && npm run test -- --run && npm run build"'
sg docker -c 'docker compose --profile test run --rm e2e \
  npx playwright test --config tests/e2e/playwright.config.ts'
```

The backend suite reports explicitly superseded Jalisco-only tests as skipped;
their national replacements are noted in `docs/hackathon/verification-results.md`.
Playwright covers national level/state switching, district observed-only API
behavior, bounded WFS, keyboard and responsive/accessibility checks. It does not
claim AA certification. GitHub Actions is configured in
`.github/workflows/ci.yml`; no claim of a GitHub-hosted run is made here.

## Entrega técnica

La entrega reproducible es `dist/national/technical.zip`; se genera y verifica
con el CLI:

```sh
sg docker -c 'docker compose exec -T api python -m participa_geo.cli deliver \
  --output-dir /workspace/dist/national --team-slug participa-geo \
  --confirm-source-license'
sg docker -c 'docker compose exec -T api python -m participa_geo.cli verify-delivery \
  --archive /workspace/dist/national/technical.zip'
```

`--confirm-source-license` incorpora los seis ZIP CCPC y 32 ZIP MGS, junto con
atribución, URL y SHA-256. La redistribución se confirma para esta entrega en
`docs/hackathon/source-licenses.md`. El ZIP excluye `.env`, secretos, cartas,
contactos y datos personales. `--skip-sources` genera una alternativa sólo con
metadatos, sin los archivos originales.
