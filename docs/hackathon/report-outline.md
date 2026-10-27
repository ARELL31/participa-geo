# Reporte metodológico — esquema de 12 páginas

Objetivo: 12 páginas A4 (aceptable 10–15). El contenido se genera desde
`DeliveryContext` (artefactos T2/T4 + escenario persistido) y no desde una
plantilla con cifras escritas a mano.

| Página | Contenido | Fuente de verdad |
|---|---|---|
| 1 | Portada, equipo/eje, modelo, corte, advertencia no causal | `manifest.json`, `DeliveryContext` |
| 2 | Resumen ejecutivo y cuatro hallazgos | métricas M0/M1, cohortes 2027 |
| 3 | Problema, preguntas y alcance; qué no hace el sistema | Spec §1–§3 |
| 4 | Fuentes CCPC, 750 observaciones, checksums y granularidad | `provenance.json` |
| 5 | Calidad, exclusiones y 85/40; reglas de nulos | `evaluation.json`, `quality.json` |
| 6 | Referencia INE 2025-12-15, identidad y huella no verificada | `reference-2025-12-15.geojson` |
| 7 | Método M0/M1, selección y protocolo temporal | `model.json`, `evaluation.json` |
| 8 | Validación 2021/2024, banda 8.56 pp, límites de cobertura | `evaluation.json` |
| 9 | Predicción 2027, semáforo, 70/85 inestables | `predictions-2027.parquet` |
| 10 | Escenarios A/B, fórmula, supuestos y etiqueta no causal | escenario persistido |
| 11 | Recomendaciones preventivas y priorización | reglas T6 |
| 12 | Limitaciones, uso responsable, reproducibilidad y entrega | manifiesto/ZIP |

Comprobaciones:

```sh
docker compose run --rm api python -m participa_geo.cli deliver \
  --scenario-id <UUID> --output-dir dist/hackathon --team-slug participa-geo \
  --confirm-source-license   # o --skip-sources
docker compose run --rm api pytest tests/integration/test_delivery.py -q
```

`pypdf` debe contar 10–15 páginas y el texto debe contener M0, 4.93, 8.90,
3.43, 8.56, 85, 40, 70, 2025-12-15 y la frase de no causalidad. Revisar la
redacción, no sólo el conteo.

Cifras reales de referencia (verificadas contra los artefactos):

- M0 seleccionado; MAE validación 2021 **4.93 pp**; M1 **8.90 pp**.
- M0 prueba 2024 **3.43 pp**; M1 **4.82 pp**.
- Banda histórica de referencia **8.56 pp** (P90; 91 errores 2021).
- 2027: **125** municipios, **85** elegibles, **40** insuficientes y **70/85**
  elegibles con categoría inestable.
- Referencia cartográfica **2025-12-15**; `footprint_status=not_verified`.
