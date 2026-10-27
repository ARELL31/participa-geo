# ADR 0001 — Referencia geográfica 2025 y estados de identidad/huella

- Fecha: 2026-10-26
- Estado: aceptada (aprobada por el usuario al aprobar el diseño)
- Alcance: T3 (persistencia PostGIS y publicación GeoServer); T4/T5/T8 consumen
  estos estados.

## Contexto

El análisis municipal de participación usa seis cortes CCPC (2009–2024) y un
objetivo 2027. Se necesita una cartografía de referencia para consultar y
publicar, y una correspondencia entre las identidades municipales de cada año y
esa referencia.

## Decisión

1. **Referencia única**: cartografía INE MGS con corte **2025-12-15** (ZIP
   SHA-256 `7b252438…`, CRS declarado EPSG:32613), transformada de forma real a
   EPSG:4326. Es la única geometría almacenada; las identidades de origen
   (2009–2024) conservan `geometry IS NULL`.
2. **Identidad ≠ huella**: se distinguen dos ejes independientes:
   `identity_status` (`verified_catalogue`/`ambiguous`/`known_changed`) y
   `footprint_status` (`verified_equal`/`not_verified`/`known_changed`). Para
   los 125 municipios la coincidencia de código/nombre da `verified_catalogue`;
   la huella queda `not_verified` (no se verificó igualdad histórica de límites).
3. **No se inventan geometrías históricas**: no se copia la geometría 2025 a
   filas etiquetadas como años anteriores, ni se redistribuyen conteos por
   intersección de secciones.
4. **El corte mayo 2023 no fue localizado**: no se afirma que no exista; se
   documenta la limitación y se usa la referencia posterior 2025.

## Consecuencias

- La API (`/territories`) y los mapas muestran la advertencia de referencia 2025;
  la serie se describe como unidades administrativas reportadas por el INE, no
  como superficie constante.
- Un municipio con identidad ambigua o cambio administrativo documentado queda
  excluido del pronóstico hasta resolverse (los estados geográficos se completan
  en T3; `None` nunca significa verificado).
- `footprint_status=verified_equal` (serie de superficie constante) queda fuera
  del alcance no verificado.

## Alternativas consideradas

- **Igualdad geométrica por concatenación INEGI**: rechazada; INE e INEGI no son
  claves equivalentes (difieren en 90/125 municipios) y la coincidencia nominal
  no prueba límites.
- **Un solo eje de "correspondencia"**: rechazada; oculta la diferencia entre
  identidad administrativa (verificable) y huella histórica (no verificada).
