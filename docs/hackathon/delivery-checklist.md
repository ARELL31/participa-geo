# Checklist de entrega PARTICIPA-GEO

Separar siempre **confirmación técnica** de **pasos humanos**. La primera puede
verificarse con comandos; la segunda no se automatiza.

## A. Confirmación técnica (verificable)

- [x] `docker compose config --quiet` sale 0.
- [x] Backend: `docker compose run --rm api pytest -q` termina sin fallos.
- [x] Web: `docker compose run --rm --no-deps web-test npm run test -- --run`.
- [x] E2E nacional real: `docker compose --profile test run --rm e2e npx playwright test --config tests/e2e/playwright.config.ts` (accesibilidad incluida; dos journeys MVP Jalisco explícitamente superseded).
- [x] `deliver` se ejecutó con **un** modo explícito de fuentes:
      `--confirm-source-license` (originales incluidos) o `--skip-sources`
      (sólo URL/checksums). Sin ninguno de los dos, el comando falla.
- [x] `deliver` nacional termina y produce `technical.zip`, `methodology.pdf`,
      `executive.pdf` y observaciones distritales 2024. Mapas/escenarios sólo
      existen para el nivel municipal y no se generan como distritos 2027.
- [x] `verify-delivery --archive dist/national/technical.zip` devuelve `complete: true` y
      todos los checksums coinciden; un paquete incompleto sale con código
      distinto de cero.
- [x] En modo `--confirm-source-license`, el ZIP incluye los seis ZIP CCPC
      nacionales y los 32 ZIP cartográficos por entidad. En modo `--skip-sources`,
      omite originales e incluye `sources/SOURCES.md` + `sources/sources.json`.
- [x] El ZIP incluye diccionarios, agregados, artefactos/métricas del modelo,
      código, docs, `docs/api/openapi.json`, reportes/mapas condicionados al
      escenario, `MANIFEST.json` y `CHECKSUMS.sha256`.
- [x] El ZIP **no** incluye `.git`, `node_modules`, cachés, `.env`, cartas
      firmadas, contactos, credenciales ni datos personales.
- [x] `pypdf` cuenta 10–15 páginas en metodología y ≤10 en la presentación.
- [x] El reporte usa los artefactos nacionales: 2,477 municipios, M0 con MAE
      12.1854 (validación 2021) y 5.5602 (prueba 2024), banda 28.8979, y
      advertencia de no causalidad.
- [x] CSV/XLSX conservan nulos (no ceros), metadatos/versiones y escapan
      prefijos de fórmula; XLSX abre con hoja de diccionario.
- [x] Las salidas espaciales se limitan por entidad/nivel; perfil distrital
      exclusivamente observado 2024 con cobertura explícita.
- [x] Los mapas A/B salen de GeoServer (capa `scenario_results`), comparten
      leyenda/corte y no hay placeholder si GIS falla.
- [x] El reporte y la presentación se generan desde artefactos/BD; una fecha de
      generación distinta no cambia los resultados.
- [x] Los checksums del paquete pasan y la ingesta nacional (54,872,712 facts)
      se reproduce desde el ZIP en cleanroom.
- [ ] Rebuild cleanroom integral pendiente: faltan en el ZIP ACCDB/CSV de historia
      seccional y `district-headquarters.txt`; el bloqueo está documentado, no se
      declara aceptación cleanroom completa.
- [x] WMS/WFS/page500/resumen 32 medidos bajo umbrales; cifras exactas en el
      informe de verificación.

Evidencia: `docs/hackathon/verification-results.md` (comandos, fechas, salida y
cobertura). La aceptación técnica no sustituye los pasos humanos de la sección B.

Comando de verificación:

```sh
  docker compose exec -T api python -m participa_geo.cli verify-delivery \
  --archive /workspace/dist/national/technical.zip
```

## B. Pasos humanos (no automatizados)

- [ ] Revisar la redacción metodológica completa (no sólo el número de páginas).
- [x] Confirmar las condiciones de uso/redistribución de INE y cartografía
      (ver `source-licenses.md`). El usuario confirmó el 2026-10-27 incluir los
      originales con atribución, URLs y checksums en el ZIP técnico; revisar el
      alcance antes de una publicación abierta.
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
- Rendimiento medido WMS/WFS/API/resumen nacional y ensayo limpio con su
  proyecto Compose, hashes, comandos y límites exactos en
  `docs/hackathon/verification-results.md`.
