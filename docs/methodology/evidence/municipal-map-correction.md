# Corrección del mapa municipal

## Causa y alcance

El mapa territorial conservaba el encuadre fijo de Jalisco y el raster del
piloto, mientras la selección municipal usaba geometría nacional. La capa WFS
municipal nacional no contiene tasas históricas; además, el límite de 500
geometrías y la primera página del catálogo omitían 70 municipios de Oaxaca.

La corrección usa observaciones municipales paginadas por entidad/año y un
contorno estatal independiente. Las tasas se unen por estado y código municipal;
ausencia/error se muestra sin tasa, nunca como cero. El encuadre se actualiza
con la entidad y el tamaño del contenedor, sin restablecer la cámara al cambiar
únicamente el año o seleccionar un municipio. La descripción queda fuera del
mapa para no tapar el contorno.

## Correcciones encontradas durante aceptación

- La consulta de última versión por estado/año se evaluaba por observación.
  Ahora selecciona versiones una vez con `DISTINCT ON`, preservando el año de
  observación, desempate por fecha/UUID y exclusión de estados nulos.
- El CSV/XLSX histórico ignoraba `territory_id`: ahora respeta la selección,
  manteniendo las exportaciones estatales/nacionales cuando no hay municipio.
  `report-rules-1.2.0` evita reutilizar artefactos anteriores sin borrarlos.

## Evidencia local

- Backend: 272 aprobadas y 76 omisiones heredadas documentadas.
- Vitest serial: 78 aprobadas; lint, typecheck y build aprobados.
- Playwright de aceptación: 17 aprobadas y 2 recorridos heredados omitidos.
- Playwright de producto: 21 aprobadas.
- Comprobación real de Jalisco (125), Nuevo León (51) y Oaxaca (570),
  paginación de Oaxaca 500+70 y selección del municipio 570.
- Pruebas de fuentes/cámara, contorno al cambiar entidad, resize/desmontaje,
  tasas cacheadas descartadas ante error y CSV/XLSX municipal de una fila.

Las primeras ejecuciones fallaron por tiempos de historia y por expectativas
del raster antiguo; se corrigieron la consulta y los contratos de prueba sin
ampliar límites del pool ni timeouts. Permanecen avisos MSW de fixtures heredados,
deprecación Starlette/httpx y tamaño del chunk MapLibre.

Esta evidencia es local: no equivale a una ejecución de GitHub Actions ni a
certificación de accesibilidad. El ZIP técnico anterior no se regeneró con este
parche; la entrega aquí corresponde al código del repositorio.
