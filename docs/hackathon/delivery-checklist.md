# Checklist de entrega PARTICIPA-GEO

Separar siempre **confirmación técnica** de **pasos humanos**. La primera puede
verificarse con comandos; la segunda no se automatiza.

## A. Confirmación técnica (verificable)

- [ ] `docker compose config --quiet` sale 0.
- [ ] Backend: `docker compose run --rm api pytest -q` termina sin fallos.
- [ ] Web: `docker compose run --rm --no-deps web-test npm run test -- --run`.
- [ ] E2E: `docker compose --profile tools run --rm --no-deps web-e2e npx playwright test`.
- [ ] `deliver` termina y produce `technical.zip`, `methodology.pdf`,
      `executive.pdf`, `scenario.csv`, `scenario.geojson`, `scenario.pdf`,
      `scenario-map.png` y `scenario-map.pdf`.
- [ ] `verify-delivery --archive .../technical.zip` devuelve `complete: true` y
      todos los checksums coinciden.
- [ ] El ZIP incluye los seis CSV CCPC de Jalisco, el ZIP cartográfico original,
      diccionarios, agregados, artefactos/métricas del modelo, código, docs,
      reportes/mapas, `MANIFEST.json` y `CHECKSUMS.sha256`.
- [ ] El ZIP **no** incluye `.git`, `node_modules`, cachés, `.env`, cartas
      firmadas, contactos, credenciales ni datos personales.
- [ ] `pypdf` cuenta 10–15 páginas en metodología y ≤10 en la presentación.
- [ ] El reporte contiene M0, 4.93, 8.90, 3.43, 8.56, 85, 40, 70, 2025-12-15 y
      la advertencia de no causalidad.
- [ ] CSV/XLSX conservan nulos (no ceros), metadatos/versiones y escapan
      prefijos de fórmula; XLSX abre con hoja de diccionario.
- [ ] GeoJSON contiene 125 geometrías EPSG:4326 de la referencia 2025-12-15 y
      valores A/B nulos cuando la información es insuficiente.
- [ ] Los mapas A/B salen de GeoServer (capa `scenario_results`), comparten
      leyenda/corte y no hay placeholder si GIS falla.
- [ ] El reporte y la presentación se generan desde artefactos/BD; una fecha de
      generación distinta no cambia los resultados.
- [ ] El paquete funciona sin depender de `/tmp/opencode`.

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
