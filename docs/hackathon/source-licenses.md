# Fuentes, licencias y condiciones de redistribución

Este documento es una revisión operativa, no un dictamen legal. Antes de una
publicación abierta, el usuario debe confirmar las condiciones aplicables.

## 1. Datos CCPC del INE (2009–2024)

- Fuente: Instituto Nacional Electoral (INE), *Conteos Censales de Participación
  Ciudadana*.
- URL de la ficha: <https://ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/>
- Archivos usados: los seis ZIP oficiales de 2009, 2012, 2015, 2018, 2021 y 2024,
  con URL, miembro, fecha de consulta y SHA-256 en `data/sources.json` y
  `data/processed/provenance.json`.
- Condición observada: la ficha pública ofrece las bases para descarga y análisis,
  pero **no publica en la misma página una licencia explícita de redistribución**.
  No se asume permiso adicional.
- Decisión del MVP: el paquete técnico sólo incluye los CSV originales de
  Jalisco cuando el usuario pasa `--confirm-source-license` después de revisar
  esta condición. Sin esa confirmación, `deliver` exige `--skip-sources` y el
  paquete lleva únicamente `sources/SOURCES.md` + `sources/sources.json` con URL
  y SHA-256, sin los originales. La API y las exportaciones analíticas sólo
  ofrecen agregados municipales.
- **Acción humana requerida:** confirmar con el INE o con la convocatoria si la
  redistribución de los originales está permitida. Si no se confirma, use
  `--skip-sources`; no se deben quitar archivos en silencio ni inventar una
  licencia.

## 2. Cartografía INE 2025-12-15

- Archivo: `data/raw/gis/ine-jalisco-2025-12-15.zip`, conservado con SHA-256.
- Uso: referencia municipal 2025, EPSG:32613 → EPSG:4326, sin redefinir el CRS.
- Condición: cartografía electoral publicada por el INE; no se localizó una
  licencia de redistribución específica en la descarga. Aplica la misma acción
  humana de confirmación del punto 1.
- Atribución obligatoria en mapas y documentos: INE, corte 2025-12-15.

## 3. Tipografía

- Inter (Regular/SemiBold), © The Inter Project Authors.
- Licencia SIL Open Font License 1.1; el texto completo está en
  `docs/hackathon/fonts/OFL.txt`.
- Se carga desde un TTF local; no se instala en el host ni se descarga en tiempo
  de ejecución.

## 4. Bibliotecas y herramientas

| Componente | Licencia | Uso |
|---|---|---|
| FastAPI / Starlette | MIT / BSD | API |
| SQLAlchemy / Alembic | MIT | Persistencia |
| pandas / numpy / pyarrow | BSD-3 / BSD-3 / Apache-2.0 | Datos |
| scikit-learn | BSD-3 | Modelo |
| GeoPandas / Shapely / pyproj | BSD-3 / BSD-3 / MIT | GIS |
| ReportLab | BSD | PDF |
| openpyxl | MIT | XLSX |
| matplotlib | PSF-based | Gráficos |
| Pillow | HPND | Composición PNG |
| pypdf | BSD-3 | Verificación de páginas |
| React / Vite / TypeScript / MapLibre / TanStack Query / Radix / Lucide | MIT / ISC / Apache-2.0 / BSD / MIT / MIT / ISC | Interfaz |

No se atribuye al equipo la propiedad intelectual de INE, cartografía, fuentes ni
bibliotecas. Las aportaciones originales del equipo se ceden según la carta que
firma el usuario; el alcance de esa cesión debe revisarse humanamente.

## 5. Qué no se incluye nunca

- Cartas firmadas, contactos, credenciales, `.env`, secretos, datos personales,
  listas nominales o cualquier identificador individual.
- `.git`, `node_modules`, cachés, resultados de pruebas y artefactos de sesión.
- Imágenes Docker. La reproducción puede requerir internet para dependencias e
  imágenes; no se promete instalación totalmente sin red.
