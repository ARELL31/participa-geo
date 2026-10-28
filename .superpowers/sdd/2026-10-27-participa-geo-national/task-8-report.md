# Task 8 — Shell nacional y perfil municipal

**Estado:** implementado, verificado y listo para commit.

## Alcance implementado

- Filtros globales persistidos en URL para nivel, entidad, territorio y año histórico; defaults municipio, todas las entidades y 2024.
- Resumen de las 32 entidades, mapa nacional WMS ligero y navegación a municipios al seleccionar una entidad.
- Consultas WFS de geometría por `participa_geo_national:municipalities`, filtradas con `state_code` y limitadas a 500 features; no se solicita WFS nacional ni se envía un año a una capa de referencia.
- Perfil municipal con observación histórica, predicción publicada si existe y enlaces a escenarios.
- El nivel distrital muestra explícitamente “Observado 2024 / perfil distrital pendiente” y evita consultas de predicción/escenarios.
- Pruebas Vitest y Playwright añadidas/actualizadas para filtros, shell, perfil y flujo nacional.

## Verificación ejecutada en este entorno

| Verificación | Resultado |
|---|---|
| Typecheck (`web-test`) | Pasa. |
| ESLint (`web-test`) | Pasa. |
| Vitest (`web-test`) | 10 archivos, 59 pruebas pasan. El timeout de la prueba de perfil se amplió a 5 s para tolerar carga concurrente del suite. |
| Build de producción (`web-test`) | Pasa. Vite advierte que el chunk MapLibre supera 500 kB minificado. |
| Playwright real (`web-e2e`, `territory.spec.ts`) | 11/11 pasan, incluida comparación nacional de 32 entidades, WMS, perfil municipal y WFS estatal. |
| API resumen 2024 | HTTP 200; devuelve 32 entidades con códigos 01–32. |
| URL WMS nacional de la UI | HTTP 200, `image/png`, PNG válido (148,530 bytes). |
| WFS nacional acotado a entidad 14 | HTTP 200; `totalFeatures=125`, 125 features recibidas, `typeNames=participa_geo_national:municipalities`, `count=500`, `state_code=14`. |
| `git diff --check` | Pasa, sin errores de whitespace. |

La causa del 503 original era el uso de la capa MVP inexistente en el workspace nacional (`participa_geo:participation_history`). Se sustituyó por la capa de geometrías nacional y el filtro estatal soportado por el gateway. La respuesta de GeoServer contiene propiedades geométricas/de referencia; las tasas históricas se consultan en la API de participación.

## Alcance excluido

- No se implementó Task 9 ni la ficha observada distrital ni reportes.

## Fix round 1

- Se añadió al mapa nacional municipal el coroplético de abstención observada de 2024, calculado con los conteos agregados `sv` y `nv`; la tabla accesible conserva las 32 entidades y marca como no disponibles las tasas nulas. El WMS permanece como referencia y el WFS temático solicita sólo `participa_geo_national:states`, con `count=32` y bbox `14.5,-118.5,32.8,-86.8`.
- La vista distrital consulta observaciones agregadas de 2024 independientemente del año histórico seleccionado, muestra cobertura y “Sin modelo 2027”, y no expone etiquetas de predicción/riesgo ni solicita el WFS municipal/estatal oculto. La acción indica “Ver observación distrital de …”.
- Typecheck (`web-test`): pasa. ESLint (`web-test`): pasa. Build de producción (`web-test`): pasa; permanece la advertencia conocida del chunk MapLibre >500 kB.
- Vitest (`web-test`): 10 archivos, 62 pruebas pasan; se añadió el fixture MSW del WFS estatal para la carga inicial de la shell.
- Playwright real (`web-e2e`, `territory.spec.ts`): 12/12 pasan, incluyendo petición WFS acotada y respuesta de 32 entidades, resumen distrital 2024 y navegación municipal.
- API real: resumen municipal 2024 HTTP 200 con 32 entidades; WFS estatal acotado HTTP 200 con 32 features. WMS verificado por Playwright HTTP 200 con `image/png`.
- `git diff --check`: pasa.
