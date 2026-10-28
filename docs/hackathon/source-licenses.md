# Fuentes, licencias y condiciones de redistribución

Este documento es una revisión operativa, no un dictamen legal. Antes de una
publicación abierta, el usuario debe confirmar las condiciones aplicables.

## 1. Datos CCPC del INE (2009–2024)

- Fuente: Instituto Nacional Electoral (INE), *Conteos Censales de Participación
  Ciudadana*.
- URL de la ficha: <https://ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/>
- Archivos usados: los seis ZIP oficiales de 2009, 2012, 2015, 2018, 2021 y 2024,
  con URL, miembro y SHA-256 en `data/sources-national.json` y
  `data/processed/national/national-ingest.json`.
- Condición observada: la ficha pública ofrece las bases para descarga y análisis,
  pero **no publica en la misma página una licencia explícita de redistribución**.
  No se asume permiso adicional.
- Decisión del MVP: el paquete técnico sólo incluye los CSV originales de
  Jalisco cuando el usuario pasa `--confirm-source-license` después de revisar
  esta condición. Sin esa confirmación, `deliver` exige `--skip-sources` y el
  paquete lleva únicamente `sources/SOURCES.md` + `sources/sources.json` con URL
  y SHA-256, sin los originales. La API y las exportaciones analíticas sólo
  ofrecen agregados municipales.
- **Confirmación de alcance:** el usuario confirmó la inclusión de fuentes
  nacionales con atribución, URL y checksums para esta entrega. `deliver
  --confirm-source-license` incluye los seis ZIP originales; el modo
  `--skip-sources` sigue disponible y omite todos los originales.

## 2. Cartografía INE nacional, plan 2023

- Archivos: `data/raw/gis/national/01.zip` … `32.zip`, conservados con sus
  checksums y atribución al INE.
- Uso: geometrías nacionales de 32 entidades para municipios y distritos
  federales plan DERFE2023; nunca se redefinen CRS.
- Condición: cartografía electoral publicada por el INE; no se localizó una
  licencia de redistribución específica en la descarga. Aplica la misma acción
  humana de confirmación del punto 1.
- Atribución obligatoria en mapas y documentos: INE, cartografía nacional plan
  DERFE2023.

## 3. Continuidad seccional y catálogo distrital INE

- ACCDB: *HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb*, URL
  oficial <https://storage.googleapis.com/mapoteca/historicos/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb>.
- `official-section-history.csv` es una exportación derivada de ese ACCDB mediante
  `scripts/export_official_section_history.sh`; el ZIP incluye ambos y el script
  para que la exportación y reconstrucción sean reproducibles.
- `district-headquarters.txt` es el catálogo de cabeceras asociado al MGS INE,
  corte 15-DIC-2025, con URL de referencia
  <https://storage.googleapis.com/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/>.
- SHA-256, bytes y nombres de miembro están en el inventario `sources/` del ZIP.
  El histórico no publica una licencia específica de redistribución. El usuario
  autorizó incluir estos materiales en esta entrega con atribución; esto no se
  presenta como licencia general para redistribución posterior.

## 4. Tamaño y modalidad de entrega

Además de los 38 ZIP originales nacionales (seis CCPC y 32 paquetes MGS, unos
**439 MiB** antes de empaquetar), el modo confirmado incluye el ACCDB histórico
(10,797,056 bytes), el CSV derivado (6,067,765 bytes) y el catálogo de cabeceras
(15,096 bytes). Los tres miembros y sus hashes/URLs se registran en
`sources/SOURCES.md`, `sources/sources.json`, `MANIFEST.json` y
`CHECKSUMS.sha256`. El ZIP técnico es de aproximadamente **440 MiB**; los bytes
y SHA-256 exactos se registran fuera del ZIP en `DELIVERY.json` y el informe Task
11, no se autoincrustan. El CSV se reproduce con
`scripts/export_official_section_history.sh`; las fuentes
originales permanecen fuera de Git. No se impone un límite de carga HTTP: el
tamaño final se registra en `DELIVERY.json` y el manifiesto. Considere el tamaño
al distribuirlo por correo o repositorios con cuotas.

## 5. Tipografía

- Inter (Regular/SemiBold), © The Inter Project Authors.
- Licencia SIL Open Font License 1.1; el texto completo está en
  `docs/hackathon/fonts/OFL.txt`.
- Se carga desde un TTF local; no se instala en el host ni se descarga en tiempo
  de ejecución.

## 6. Bibliotecas y herramientas

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

## 7. Qué no se incluye nunca

- Cartas firmadas, contactos, credenciales, `.env`, secretos, datos personales,
  listas nominales o cualquier identificador individual.
- `.git`, `node_modules`, cachés, resultados de pruebas y artefactos de sesión.
- Imágenes Docker. La reproducción puede requerir internet para dependencias e
  imágenes; no se promete instalación totalmente sin red.
