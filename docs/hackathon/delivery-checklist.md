# Checklist de entrega PARTICIPA-GEO

Separar siempre **confirmación técnica** de **pasos humanos**. La primera puede
verificarse con comandos; la segunda no se automatiza.

## A. Confirmación técnica (verificable)

- [x] `docker compose config --quiet` sale 0.
- [x] Backend: `docker compose run --rm api pytest -q` termina sin fallos.
- [x] Web: `docker compose run --rm --no-deps web-test npm run test -- --run`.
- [x] E2E: `docker compose --profile tools run --rm --no-deps web-e2e npx playwright test`.
- [x] `deliver` se ejecutó con **un** modo explícito de fuentes:
      `--confirm-source-license` (originales incluidos) o `--skip-sources`
      (sólo URL/checksums). Sin ninguno de los dos, el comando falla.
- [x] `deliver` termina y produce `technical.zip`, `methodology.pdf`,
      `executive.pdf`, `scenario.csv`, `scenario.geojson`, `scenario.pdf`,
      `scenario-map.png` y `scenario-map.pdf`.
- [x] `verify-delivery --archive .../technical.zip` devuelve `complete: true` y
      todos los checksums coinciden; un paquete incompleto sale con código
      distinto de cero.
- [x] En modo `--confirm-source-license`, el ZIP incluye los seis CSV CCPC de
      Jalisco y el ZIP cartográfico original. En modo `--skip-sources`, no los
      incluye y sí lleva `sources/SOURCES.md` + `sources/sources.json` con URL y
      SHA-256.
- [x] El ZIP incluye diccionarios, agregados, artefactos/métricas del modelo,
      código, docs, `docs/api/openapi.json`, reportes/mapas condicionados al
      escenario, `MANIFEST.json` y `CHECKSUMS.sha256`.
- [x] El ZIP **no** incluye `.git`, `node_modules`, cachés, `.env`, cartas
      firmadas, contactos, credenciales ni datos personales.
- [x] `pypdf` cuenta 10–15 páginas en metodología y ≤10 en la presentación.
- [x] El reporte contiene M0, 4.93, 8.90, 3.43, 8.56, 85, 40, 70, 2025-12-15 y
      la advertencia de no causalidad.
- [x] CSV/XLSX conservan nulos (no ceros), metadatos/versiones y escapan
      prefijos de fórmula; XLSX abre con hoja de diccionario.
- [x] GeoJSON contiene 125 geometrías EPSG:4326 de la referencia 2025-12-15 y
      valores A/B nulos cuando la información es insuficiente.
- [x] Los mapas A/B salen de GeoServer (capa `scenario_results`), comparten
      leyenda/corte y no hay placeholder si GIS falla.
- [x] El reporte y la presentación se generan desde artefactos/BD; una fecha de
      generación distinta no cambia los resultados.
- [x] El paquete funciona sin depender de `/tmp/opencode`.

Evidencia: `docs/hackathon/verification-results.md` (comandos, fechas, salida y
cobertura). La aceptación técnica no sustituye los pasos humanos de la sección B.

Comando de verificación:

```sh
docker compose run --rm api python -m participa_geo.cli verify-delivery \
  --archive dist/hackathon/technical.zip
```

## B. Pasos humanos (no automatizados)

- [ ] Revisar la redacción metodológica completa (no sólo el número de páginas).
- [ ] Confirmar las condiciones de uso/redistribución de INE y cartografía
      (ver `source-licenses.md`); si no están claras, sustituir originales por
      checksums e instrucciones antes de publicar.
- [ ] Firmar cartas de cesión/declaratoria y revisar el alcance de la cesión.
- [ ] Integrar las cartas en un espacio privado, **fuera** de Git, API,
      contenedores y ZIP técnico.
- [ ] Revisar atribuciones de librerías, datos y cartografía; no atribuir
      propiedad intelectual de terceros al equipo.
- [ ] Confirmar que no hay datos personales, contactos ni identificadores
      individuales en el paquete final.
- [ ] Revisar el ZIP institucional final y realizar el envío por el canal
      humano acordado. No se automatizan firmas ni correo.

## C. Evidencia a conservar

- Salida de pruebas backend/frontend/E2E.
- Hash y tamaño de `technical.zip`, más la salida de `verify-delivery`.
- Conteo de páginas y extracto de texto de ambos PDF.
- Versión de modelo, corte, escenario, supuestos y hashes de entrada.
- Fecha/hora de generación (metadato variable; no se exige ZIP binariamente
  idéntico).
