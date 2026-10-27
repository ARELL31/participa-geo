# Referencia geográfica — INE MGS 15-DIC-2025

## Fuente verificada

| Campo | Valor |
|---|---|
| Fuente | INE, Marco Geográfico y Secciones (producto `mgs`), entidad Jalisco (`14`), Shapefile. |
| API | `https://cartografia.ine.mx/sige8/api/bases/?producto=mgs&entidad=14&formato=Shapefile` |
| ZIP | `https://cartografia.ine.mx/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/14.zip` |
| Archivo local | `data/raw/gis/ine-jalisco-2025-12-15.zip` (git-ignored) |
| SHA-256 del ZIP | `7b252438a67d904a42a7b912ff29bef74a2ed79675a609143e74a592ef872a50` |
| Fecha del corte | **2025-12-15** (no 2023-05) |
| Miembro usado | `14/MUNICIPIO.shp` |
| Registros | 125 municipios, 125 geometrías Polygon/MultiPolygon no nulas (122 Polygon, 3 MultiPolygon) |
| CRS declarado | `EPSG:32613` (WGS84 / UTM 13N) |
| Códigos/nombres | Códigos INE `001`–`125` y nombres coincidentes con los seis CSV CCPC (identidad de catálogo). |

## Transformación de CRS (real, no reetiquetado)

La geometría se importa como **EPSG:4326** tras una transformación real
`.to_crs(4326)` desde `EPSG:32613`; jamás se usa `.set_crs(4326)` sobre las
coordenadas UTM. La verificación en PostGIS registra `source_srid = 32613` y
`ST_SRID(geometry) = 4326`, y comprueba que las coordenadas caen dentro del
recuadro lon/lat de Jalisco (`-107..-100`, `18..23`). Una geometría vacía o
inválida se rechaza **antes** de intentar cualquier reparación.

## Estados de identidad y huella

- `identity_status = verified_catalogue`: la coincidencia única de código INE,
  entidad y nombre normalizado entre los seis CSV CCPC y el catálogo INE 2025
  permite una serie de identidad administrativa. Esto **no** prueba igualdad
  histórica de límites.
- `footprint_status = not_verified`: la coincidencia de identidad **no** es
  igualdad geométrica histórica. La serie se describe como unidades
  administrativas reportadas por el INE sobre la referencia 2025, no como una
  serie de superficie constante.

Los dos estados se almacenan por separado en `territory_correspondence` (750
filas: 125 municipios × 6 años) y nunca se infiere equivalencia por
concatenación INEGI.

## Limitación aprobada

No se encontró el corte **mayo 2023** en los mecanismos consultados; no se
afirma que no exista. La cartografía INE 2025 se usa como **referencia
posterior** para la consulta municipal y los escenarios 2027. No se hace
redistribución de conteos por intersección de secciones de distintos años, ni se
presentan los mapas 2009–2024 como si mostraran límites contemporáneos de cada
elección. Las identidades de origen conservan `geometry IS NULL`; sólo la
referencia 2025 recibe el polígono descargado. Esta limitación fue aceptada por
el usuario al aprobar el diseño (Spec §5, §17).
