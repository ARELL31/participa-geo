# Auditoría nacional PARTICIPA-GEO — CCPC y cartografía INE

**Fecha de ejecución:** 2026-10-27  
**Alcance:** evidencia de solo lectura para decidir la arquitectura nacional (municipios + distritos federales, 32 entidades). No se modificó el repositorio, no se implementó producto y no se instalaron paquetes en el host. Descargas y notas en `/tmp/opencode`.  
**Repo de referencia:** `/home/arell31/participa-geo` (rama `design/national-expansion`, intacta).  
**Evidencia:** `/tmp/opencode/participa-geo-national-audit/`

---

## 0. Resumen ejecutivo

1. **Los seis ZIP de CCPC son íntegros y completos:** cada año contiene exactamente **32 CSV** (uno por entidad) y un TXT de diccionario. Se procesaron **54,872,712 filas** en total, sin muestreo. Tamaño: **292.5 MB comprimidos / 3.73 GB descomprimidos**.
2. **La calidad transaccional es alta:** no hay claves analíticas duplicadas, no hay `MPIOCVE` vacío, no hay `EDOCVE` fuera de 01–32, no hay valores negativos y **LN = SV + NV + NS en las 54.87 millones de filas** (0 descuadres).
3. **Pero el campo `DEF` no es histórico.** El diccionario dice explícitamente que 2009–2021 usan el marco **DERFE 2021** y 2024 el marco **DERFE 2023**. Lo confirmamos empíricamente: entre 2009 y 2021 la asignación sección→distrito es **idéntica** (0 cambios en 63,859 secciones comunes). No hay evidencia de distritos históricos 2009–2018 en este dataset; hay dos “fotos” geográficas: 2021 y 2023.
4. **2024 sí cambió el mapa:** 13,183 de 67,976 secciones comunes (**19.39%**) cambian de distrito frente a 2021; 7 claves de distrito salen y 7 entran en 12 entidades. El total nacional sigue siendo **300 distritos**.
5. **Municipios:** pasan de 2,458 (2009) a 2,477 (2024); hay **19 altas y 0 bajas**, más **3 ausencias de datos en 2012** que reaparecen en 2015. La ausencia de una clave no implica que el municipio no existiera.
6. **Cartografía MGS:** las 32 entidades están disponibles (HTTP 200; 167.0 MB de ZIPs). Cada ZIP trae `ENTIDAD`, `MUNICIPIO`, `DISTRITO_FEDERAL`, `DISTRITO_LOCAL` y `SECCION`. El inventario nacional es **2,477 municipios, 300 distritos federales, 679 distritos locales y 73,268 secciones**, con CRS UTM 11N–16N y sin nulos en DBF.
7. **Correspondencia municipio–distrito:** la capa `SECCION` contiene `municipio`, `distrito_f` y `distrito_l`; de ahí se derivan **2,581 pares municipio–distrito** que coinciden **exactamente** con el catálogo oficial. **72 municipios están partidos entre 2 y 5 distritos** (máximo 5 en BC, CDMX, Edomex y Puebla). No existe una relación 1:1 municipio→distrito.
8. **Distritos sin nombre:** `DISTRITO_FEDERAL` sólo tiene clave (`distrito_f`), un campo numérico `tipo` y `control`; no hay nombre. El catálogo “Con Cabeceras Distritales” da una cabecera (municipio/localidad) por distrito para etiquetar.
9. **WMS actual funciona, WFS no existe:** WMS 1.1.1 en EPSG:4326/3857, capa `DISTRITO` y `MUNICIPIO` renderizan; no hay WFS, todas las capas tienen `queryable="0"` (GetFeatureInfo falla) y `DISTRITO_ANTERIOR` está declarada pero su GetMap falla. No sirve como API de atributos ni como fuente histórica.
10. **Recomendación:** almacenar CCPC en su grano nativo (entidad–municipio–sección–sexo–edad–año), agregar a distritos **por sección**, y versionar toda identidad geográfica (`DEF_2021`, `DEF_2023`, municipio con `valid_from/valid_to`). No usar `DEF` “pelón” como clave entre años ni asignar un distrito único a un municipio.

---

## 1. Método y reproducibilidad

- Descarga directa de los seis ZIP desde las URLs del inventario CCPC, con `curl -L` y reintentos; verificación `unzip -t`.
- Lectura en streaming desde el ZIP (sin extraer los 3.7 GB): parser por comas para todas las filas y parser CSV formal para las líneas con campos entrecomillados (Oaxaca, municipio 549).
- Conteos exactos por entidad y año; no estimaciones.
- Comparación de conjuntos de claves y de asignaciones sección→distrito entre años.
- Cartografía: consulta a la API pública para las 32 entidades; descarga de los 32 ZIP; lectura directa de DBF/SHP/PRJ con código Python propio (sin GDAL/GEOS).
- WMS: `GetCapabilities` y `GetMap` reales; prueba de WFS y de `GetFeatureInfo`.
- Todos los scripts, JSON, CSV y hashes quedaron en `/tmp/opencode/participa-geo-national-audit/`.

**Nota metodológica:** el barrido inicial por comas falló en 1,778–1,866 líneas por año de Oaxaca porque el nombre del municipio 549 contiene una coma y va entrecomillado. Esas filas son CSV válidas; se re-auditaron con `csv.reader` y se corrigieron los agregados de Oaxaca. No hay otras líneas entrecomilladas en los seis años.

---

## 2. CCPC nacional

### 2.1 Integridad y volumen

| Año | ZIP MB | Descomprimido MB | CSV | Filas | Municipios | Distritos | Secciones | DEF faltante | % DEF faltante |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2009 | 40.2 | 587.0 | 32 | 8,706,843 | 2,458 | 300 | 64,934 | 28,477 | 0.327% |
| 2012 | 39.5 | 580.1 | 32 | 8,604,456 | 2,455 | 300 | 65,599 | 15,677 | 0.182% |
| 2015 | 42.6 | 613.2 | 32 | 9,106,059 | 2,458 | 300 | 68,362 | 0 | 0.000% |
| 2018 | 43.4 | 623.3 | 32 | 9,251,122 | 2,463 | 300 | 68,408 | 0 | 0.000% |
| 2021 | 44.4 | 635.5 | 32 | 9,430,502 | 2,468 | 300 | 68,812 | 0 | 0.000% |
| 2024 | 82.4 | 688.0 | 32 | 9,773,730 | 2,477 | 300 | 70,751 | 0 | 0.000% |
| **Total** | **292.5** | **3,727.2** | **192** | **54,872,712** | — | — | — | **44,154** | — |

- Los seis ZIP pasan `unzip -t`; 32 CSV y 1 TXT por año; 0 archivos extraños.
- Los tamaños descomprimidos coinciden con la suma de miembros del inventario. La diferencia de ~9.9 KB por ZIP entre “suma de miembros comprimidos” y archivo descargado es overhead del contenedor ZIP.
- `Last-Modified` HTTP: 2009–2021 = **2022-04-18**; 2024 = **2025-08-13**. Los cinco años históricos fueron republicados juntos, consistente con el retrofit al marco 2021.
- Hashes SHA-256 de los seis ZIPs y de los 32 ZIPs cartográficos en `SHA256SUMS.txt`.

**URLs CCPC usadas** (idénticas a `ccpc-inventory.json`):

```
https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2009.zip
https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2012.zip
https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2015.zip
https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2018.zip
https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2021.zip
https://ine.mx/wp-content/uploads/2025/08/DatosAbiertos_DECEyEC_ConteosCensales2024.zip
```

### 2.2 Cobertura y conteos por entidad

Tabla completa por entidad y año: `ccpc_entity_year.csv` (192 filas) y pivotes `ccpc_municipality_counts_by_entity_year.csv` / `ccpc_district_counts_by_entity_year.csv`.

Hechos comprobados:

- **32 entidades presentes en todos los años** (suma de `n_mpio` y `n_def` por entidad; no hay entidades vacías).
- **300 distritos federales distintos en cada año** (suma nacional), pero con **distribución estatal distinta** entre 2021 y 2024.
- **Municipios distintos:** 2,458 (2009), 2,455 (2012), 2,458 (2015), 2,463 (2018), 2,468 (2021), 2,477 (2024).
- **Secciones distintas:** 64,934 → 65,599 → 68,362 → 68,408 → 68,812 → 70,751.
- **`MPIOCVE` vacío:** 0 en todos los años. **`MPIOCVE` inválido (≤0):** 0.
- **`DEF` inválido (no numérico, ≤0 o >99):** 0 en todos los años. Los faltantes de 2009/2012 son espacios en blanco, no códigos inválidos.
- **`EDOCVE` fuera de 01–32:** 0. Ojo: viene como entero (`1`, no `01`); hay que normalizar a dos dígitos.
- **Duplicados de clave analítica** `(EDOCVE, MPIOCVE, SECCION, SEXO, EDAD)`: **0** en los seis años. Duplicados incluyendo `DEF`: **0**.
- **Secciones asignadas a más de un `DEF`:** **0** en todos los años. La sección es una unidad atómica para distrito.

### 2.3 Municipios y distritos por entidad (2024 vs 2021)

Los conteos de distritos 2021/2024 vienen de CCPC; municipios, distritos locales y secciones vienen del MGS 2025 (los municipios 2024 de CCPC coinciden: 2,477).

| Ent | Municipios (MGS) | Dist. fed. 2021 | Dist. fed. 2024 | Δ | Dist. locales (MGS) | Secciones (MGS) | UTM | ZIP MB |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 01 | 11 | 3 | 3 | +0 | 18 | 736 | 13N | 1.0 |
| 02 | 7 | 8 | 9 | +1 | 17 | 2,254 | 11N | 4.7 |
| 03 | 5 | 2 | 2 | +0 | 16 | 535 | 12N | 2.6 |
| 04 | 13 | 2 | 2 | +0 | 21 | 555 | 15N | 1.7 |
| 05 | 38 | 7 | 8 | +1 | 16 | 1,872 | 14N | 2.7 |
| 06 | 10 | 2 | 2 | +0 | 16 | 430 | 13N | 1.3 |
| 07 | 124 | 13 | 13 | +0 | 24 | 2,296 | 15N | 10.1 |
| 08 | 67 | 9 | 9 | +0 | 22 | 3,311 | 13N | 5.2 |
| 09 | 16 | 24 | 22 | -2 | 33 | 5,589 | 14N | 2.6 |
| 10 | 39 | 4 | 4 | +0 | 15 | 1,415 | 13N | 4.1 |
| 11 | 46 | 15 | 15 | +0 | 22 | 3,357 | 14N | 6.6 |
| 12 | 85 | 9 | 8 | -1 | 28 | 2,718 | 14N | 7.4 |
| 13 | 84 | 7 | 7 | +0 | 18 | 1,894 | 14N | 5.1 |
| 14 | 125 | 20 | 20 | +0 | 20 | 4,080 | 13N | 10.0 |
| 15 | 125 | 41 | 40 | -1 | 45 | 7,052 | 14N | 8.0 |
| 16 | 113 | 12 | 11 | -1 | 24 | 2,825 | 14N | 10.1 |
| 17 | 36 | 5 | 5 | +0 | 12 | 949 | 14N | 1.8 |
| 18 | 20 | 3 | 3 | +0 | 18 | 1,011 | 13N | 2.5 |
| 19 | 51 | 12 | 14 | +2 | 26 | 3,114 | 14N | 4.2 |
| 20 | 570 | 10 | 10 | +0 | 25 | 2,564 | 14N | 13.4 |
| 21 | 217 | 15 | 16 | +1 | 26 | 2,965 | 14N | 11.7 |
| 22 | 18 | 5 | 6 | +1 | 15 | 1,090 | 14N | 2.2 |
| 23 | 11 | 4 | 4 | +0 | 15 | 1,151 | 16N | 2.1 |
| 24 | 58 | 7 | 7 | +0 | 15 | 1,901 | 14N | 3.7 |
| 25 | 20 | 7 | 7 | +0 | 24 | 3,855 | 13N | 4.1 |
| 26 | 72 | 7 | 7 | +0 | 21 | 1,667 | 12N | 4.0 |
| 27 | 17 | 6 | 6 | +0 | 21 | 1,191 | 15N | 3.8 |
| 28 | 43 | 9 | 8 | -1 | 22 | 2,220 | 14N | 3.2 |
| 29 | 60 | 3 | 3 | +0 | 15 | 634 | 14N | 1.6 |
| 30 | 212 | 20 | 19 | -1 | 30 | 5,004 | 14N | 16.7 |
| 31 | 106 | 5 | 6 | +1 | 21 | 1,240 | 16N | 1.1 |
| 32 | 58 | 4 | 4 | +0 | 18 | 1,793 | 13N | 7.6 |

**Cambios de distrito 2021→2024 (12 entidades, −7/+7, total 300):**

| Entidad | 2021 | 2024 | Claves que salen | Claves que entran |
|---|---:|---:|---|---|
| 02 Baja California | 8 | 9 | — | 09 |
| 05 Coahuila | 7 | 8 | — | 08 |
| 09 CDMX | 24 | 22 | 23, 24 | — |
| 12 Guerrero | 9 | 8 | 09 | — |
| 15 Estado de México | 41 | 40 | 41 | — |
| 16 Michoacán | 12 | 11 | 12 | — |
| 19 Nuevo León | 12 | 14 | — | 13, 14 |
| 21 Puebla | 15 | 16 | — | 16 |
| 22 Querétaro | 5 | 6 | — | 06 |
| 28 Tamaulipas | 9 | 8 | 09 | — |
| 30 Veracruz | 20 | 19 | 20 | — |
| 31 Yucatán | 5 | 6 | — | 06 |
| **Total** | **300** | **300** | **7** | **7** |

### 2.4 Comparación de claves y cambios de delimitación

| Comparación | Municipios nuevos | Municipios ausentes | Distritos nuevos | Distritos retirados | Municipios con conjunto DEF distinto | Secciones comunes con DEF distinto |
|---|---:|---:|---:|---:|---:|---:|
| 2009→2012 | 0 | 3 | 0 | 0 | 0/2,455 (0.0%) | 0/63,568 (0.00%) |
| 2012→2015 | 3 | 0 | 0 | 0 | 0/2,455 (0.0%) | 0/65,378 (0.00%) |
| 2015→2018 | 5 | 0 | 0 | 0 | 11/2,458 (0.4%) | 0/68,361 (0.00%) |
| 2018→2021 | 5 | 0 | 0 | 0 | 12/2,463 (0.5%) | 0/67,633 (0.00%) |
| 2021→2024 | 9 | 0 | 7 | 7 | 563/2,468 (22.8%) | 13,183/67,976 (19.39%) |
| 2009→2024 | 19 | 0 | 7 | 7 | 554/2,458 (22.5%) | 11,850/63,052 (18.79%) |

Lectura correcta de esta tabla:

- **2009–2021 no muestra cambios de asignación sección→DEF.** No es que la geografía electoral no haya cambiado en la realidad; es que el campo `DEF` de todos esos años fue reasignado al marco 2021. Comparar 2009 con 2012 no revela el mapa de 2009.
- **2021→2024 sí es un cambio de plan:** 19.39% de las secciones comunes cambian de distrito. En 12 entidades cambia el número de distritos; en las demás puede cambiar el polígono sin cambiar el total.
- **El mismo número de distrito no implica el mismo polígono.** Ejemplo: Jalisco conserva 20 distritos, pero 1,039 de 3,559 secciones comunes (29.2%) cambian de `DEF` entre 2021 y 2024. Tlaxcala cambia 48.0%; Querétaro 46.4%.
- **Cambios municipales ≠ cambios distritales:** los 11 y 12 municipios con conjunto DEF distinto en 2015–2021 se explican por creación/segmentación de municipios (p. ej., Chiapas 120–124), no por un nuevo plan federal.
- **No se puede distinguir “cambio de polígono” de “renumeración”** sin las geometrías de ambos planes. La evidencia de secciones reasignadas es compatible con ambas; la conclusión segura es que la clave no es una identidad geográfica estable.

**Altas municipales 2021→2024 (9):**

| Entidad | Clave | Municipio |
|---|---|---|
| 02 | 006 | San Quintín |
| 02 | 007 | San Felipe |
| 12 | 082 | Ñuu Savi |
| 12 | 083 | Las Vigas |
| 12 | 084 | San Nicolás |
| 12 | 085 | Santa Cruz del Rincón |
| 17 | 036 | Hueyapan |
| 25 | 019 | El Dorado |
| 25 | 020 | Juan José Ríos |

En 2009→2024 hay 19 altas y 0 bajas. Las altas de 2015–2021 incluyen Chiapas 119–124, Campeche 012–013, Morelos 034–035; las de 2021–2024 son las nueve de la tabla.

### 2.5 Anomalías y reconciliación

| Año | Filas | DEF en blanco | % filas | Secciones sin DEF | Entidades afectadas | EDAD >120 | Duplicados | Descuadre LN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2009 | 8,706,843 | 28,477 | 0.327% | 318 | 30 | 212 | 0 | 0 |
| 2012 | 8,604,456 | 15,677 | 0.182% | 221 | 28 | 52 | 0 | 0 |
| 2015 | 9,106,059 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2018 | 9,251,122 | 0 | 0 | 0 | 0 | 51 | 0 | 0 |
| 2021 | 9,430,502 | 0 | 0 | 0 | 0 | 38 | 0 | 0 |
| 2024 | 9,773,730 | 0 | 0 | 0 | 0 | 18 | 0 | 0 |

1. **`DEF`/`DEL` en blanco en 2009 y 2012.** No son celdas vacías: contienen **un espacio**. Afectan 28,477 filas/318 secciones (2009) y 15,677/221 (2012). **Las 318 y 221 secciones existen en CCPC pero ninguna existe en el MGS 2025**: son secciones obsoletas/renumeradas. No deben imputarse a un distrito; deben quedar como “sin distrito” o resolverse con la cartografía histórica.
2. **Ausencias de municipios en 2012.** Faltan Chiapas 117 (San Andrés Duraznal) y Oaxaca 144 (San Francisco Nuxaño) y 218 (San Juan Teita), presentes en 2009 y 2015. Es un hueco de datos, no una desaparición. No publicar 0: publicar “sin dato”.
3. **Edades fuera de rango.** 212 registros en 2009, 52 en 2012, 51 en 2018, 38 en 2021 y 18 en 2024 con `EDAD` entre 121 y 137; en 2015 no hay. Son pocos y no afectan la reconciliación. No se corrigieron.
4. **Campos entrecomillados.** Oaxaca, municipio 549: 1,778–1,866 líneas por año con nombre entrecomillado y coma. Un `split(",")` ingenuo rompe la fila; un parser CSV formal la lee bien. El nombre además está truncado (“H VILLA TEZOATLAN SEGURA Y LUNA CUNA IND OAX”), por lo que **hay que usar claves, no nombres**.
5. **Claves sin cero a la izquierda.** `EDOCVE`, `MPIOCVE`, `DEF` vienen como enteros (`1`, `36`, `3`), no como `01`, `036`, `03`. Normalizar a strings con `zfill(2/3)` al ingerir; no usar el valor crudo como clave.
6. **Reconciliación exacta.** Para las 54,872,712 filas, `LN = SV + NV + NS` en todos los casos; no hay negativos ni nulos en esas cuatro columnas. Los faltantes de `DEF` no rompen la reconciliación.
7. **Sin duplicados.** La clave `(entidad, municipio, sección, sexo, edad)` es única en cada entidad-año; añadir `DEF` tampoco genera duplicados.
8. **Sin códigos inválidos.** No hay `EDOCVE` fuera de 01–32 ni `MPIOCVE`/`DEF` ≤0 o no numéricos. El único problema de `DEF` es el espacio en blanco de 2009/2012.

### 2.6 Qué falta para una auditoría nacional completa

- **Fechas y changelog por archivo:** sólo tenemos `Last-Modified` HTTP (2022-04-18 para 2009–2021; 2025-08-13 para 2024). No hay versión, folio, acuerdo o nota de cambios por CSV.
- **Diccionario de códigos:** el TXT describe campos, pero no incluye catálogo de municipios, claves de distrito, ni historia de altas/bajas municipales. Hace falta el catálogo de municipios y los decretos de creación.
- **Correspondencias históricas:** el ACCDB `HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb` (10.8 MB, disponible en el bucket) y los acuerdos de distritación 2017 son las fuentes candidatas; no se abrieron (no hay `mdbtools` en el entorno).
- **Geometrías DERFE 2021 y anteriores:** no las localizamos como shapefile en el listado público. Sin ellas no se puede reconstruir el polígono histórico de 2009–2018.
- **Validación topológica completa:** no hay GEOS/GDAL; sólo se validaron cierre de anillos, área no nula y coordenadas finitas.
- **Términos de uso/licencia** para redistribuir cartografía y datos, no auditados.

---

## 3. Cartografía nacional

### 3.1 Disponibilidad MGS para las 32 entidades

Patrón verificado:

```
https://cartografia.ine.mx/sige8/api/bases/?producto=mgs&entidad=14&formato=Shapefile
  → [{"path":"MGS_UTM_SHAPEFILE_15DIC2025/","archivo":"14.zip"}]

https://storage.googleapis.com/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/14.zip
  → ZIP real (10,031,205 bytes)
```

- **32/32 entidades: API HTTP 200 y archivo HTTP 200.** No hubo entidades faltantes ni respuestas vacías.
- Tamaño total: **166,955,296 bytes (167.0 MB)**; rango 1,039,202 (01) a 16,711,238 (30).
- Fecha de corte en la ruta: **15-DIC-2025**; `Last-Modified` del ZIP de Jalisco: 2026-02-17.
- Cada ZIP contiene las cinco capas (`ENTIDAD`, `MUNICIPIO`, `DISTRITO_FEDERAL`, `DISTRITO_LOCAL`, `SECCION`) con DBF/SHP/SHX/PRJ/CPG.
- Lista completa de URL, HTTP y bytes: `carto/mgs_api_32.json` y `carto/mgs_api_32.csv`.

**Muestra de disponibilidad (las 32 están en el CSV):**

| Entidad | API | Archivo | Bytes | UTM | Municipios | Dist. fed. |
|---|---:|---:|---:|---|---:|---:|
| 01 Aguascalientes | 200 | 200 | 1,039,202 | 13N | 11 | 3 |
| 02 Baja California | 200 | 200 | 4,670,339 | 11N | 7 | 9 |
| 09 CDMX | 200 | 200 | 2,622,704 | 14N | 16 | 22 |
| 14 Jalisco | 200 | 200 | 10,031,205 | 13N | 125 | 20 |
| 15 Estado de México | 200 | 200 | 7,995,529 | 14N | 125 | 40 |
| 20 Oaxaca | 200 | 200 | 13,397,170 | 14N | 570 | 10 |
| 30 Veracruz | 200 | 200 | 16,711,238 | 14N | 212 | 19 |
| 32 Zacatecas | 200 | 200 | 7,637,356 | 13N | 58 | 4 |

### 3.2 Inspección de muestras: Jalisco (14), CDMX (09), Oaxaca (20)

| Entidad | Capa | Registros | Campos DBF | CRS (.prj) | Nulos |
|---|---|---:|---|---|---:|
| 14 Jalisco | ENTIDAD | 1 | `id, entidad, nombre, circunscri, crc, control` | WGS_1984_UTM_Zone_13N | 0 |
| 14 | MUNICIPIO | 125 | `id, entidad, municipio, nombre, control` | WGS_1984_UTM_Zone_13N | 0 |
| 14 | DISTRITO_FEDERAL | 20 | `id, entidad, tipo, distrito_f, control` | WGS_1984_UTM_Zone_13N | 0 |
| 14 | DISTRITO_LOCAL | 20 | `id, entidad, distrito_l` | WGS_1984_UTM_Zone_13N | 0 |
| 14 | SECCION | 4,080 | `id, entidad, distrito_f, distrito_l, municipio, seccion, tipo, control` | WGS_1984_UTM_Zone_13N | 0 |
| 09 CDMX | ENTIDAD | 1 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 09 | MUNICIPIO | 16 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 09 | DISTRITO_FEDERAL | 22 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 09 | DISTRITO_LOCAL | 33 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 09 | SECCION | 5,589 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 20 Oaxaca | ENTIDAD | 1 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 20 | MUNICIPIO | 570 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 20 | DISTRITO_FEDERAL | 10 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 20 | DISTRITO_LOCAL | 25 | idéntico | WGS_1984_UTM_Zone_14N | 0 |
| 20 | SECCION | 2,564 | idéntico | WGS_1984_UTM_Zone_14N | 0 |

- El esquema es **uniforme en las 32 entidades** para las cinco capas.
- `DISTRITO_FEDERAL` **no tiene campo de nombre**: sólo `distrito_f` (numérico) y `tipo` (numérico, valores 6–14). `MUNICIPIO` sí tiene `nombre`.
- `ENTIDAD` tiene `nombre`, `circunscri` y `crc`.
- Todas las capas tienen **0 valores nulos/vacíos** en DBF en las 32 entidades.
- CRS: **WGS 1984 UTM**, zonas **11N a 16N** según entidad. No hay un CRS nacional único en los ZIP por entidad.

### 3.3 Conteo nacional (las 32 entidades)

| Capa | Registros | Vértices | Partes | DBF+SHP |
|---|---:|---:|---:|---:|
| ENTIDAD | 32 | — | — | 7.2 MB |
| MUNICIPIO | 2,477 | 2,217,488 | 3,114 | 36.0 MB |
| DISTRITO_FEDERAL | 300 | 934,245 | 727 | 15.0 MB |
| DISTRITO_LOCAL | 679 | — | — | 20.2 MB |
| SECCION | 73,268 | — | — | 172.5 MB |

- **300 distritos federales** exactos, confirmados por dos vías: suma de `DISTRITO_FEDERAL.dbf` (300) y catálogo oficial `Catálogo de Distritos.txt` (300 filas).
- La distribución estatal de 2024 coincide **exactamente** con el catálogo oficial vigente (corte 19ENE2026; por ejemplo, CDMX 22, Edomex 40, Jalisco 20, Oaxaca 10, Veracruz 19).
- **2,477 municipios** coincide con el catálogo de municipios (2,477).
- **73,268 secciones** coincide con el catálogo de secciones por distrito (73,268 filas, 73,268 secciones únicas).
- **679 distritos locales** es el total de la capa `DISTRITO_LOCAL` (no equivale a los 300 federales).

### 3.4 Distritos: nombre y correspondencia municipio–distrito

- **No hay nombre de distrito en la cartografía.** El campo `distrito_f` es la clave; `tipo` es un código numérico sin diccionario en el ZIP. Para etiquetas hay que usar “Distrito NN” o el catálogo de cabeceras.
- `Catálogo de Distritos Con Cabeceras Distritales.txt` contiene **300 filas, una por distrito**, con entidad, distrito, municipio y localidad de cabecera. No es un nombre oficial del distrito, pero sirve para etiquetar (“Distrito 05 — cabecera X”).
- **La correspondencia municipio–distrito sí está en la cartografía**, en la capa `SECCION`: cada sección trae `municipio` y `distrito_f`.
- Derivamos los pares `(entidad, municipio, distrito_f)` desde `SECCION` y los comparamos con el catálogo `Municipios y Distritos`: **2,581 pares en ambos, 0 diferencias, 0 pares faltantes**. Es una coincidencia exacta, no una aproximación.
- **72 municipios están partidos entre más de un distrito federal; máximo 5.** Los casos con máximo 5 están en BC (02), CDMX (09), Edomex (15) y Puebla (21). Oaxaca, con 570 municipios, tiene máximo 2.
- Consecuencia: **no existe una tabla municipio→distrito 1:1**. Cualquier asignación de un distrito único a un municipio es una decisión analítica que pierde información.

### 3.5 Validez geométrica y CRS

- Se validaron **los 300 polígonos de distrito federal y los 2,477 de municipio** de las 32 entidades: **0 anillos sin cerrar, 0 anillos de área cero, 0 coordenadas no finitas**.
- No se hizo validación topológica completa (auto-intersecciones, huecos, solapamientos) porque no hay GEOS/GDAL en el entorno. Es una **validación básica**, no una certificación OGC.
- Los 300 distritos tienen claves `1..n` por entidad, sin duplicados ni huecos, y `entidad` consistente con el ZIP.
- Los shapefiles están en UTM por entidad; para una capa nacional hay que reproyectar (p. ej. a EPSG:6372 o EPSG:4326) o usar el producto nacional en CCL.

**Producto nacional en CCL (no inspeccionado):**

```
https://storage.googleapis.com/mapoteca/MGS_CCL/SHAPEFILE.7z
HTTP 200 · 85,681,402 bytes · Last-Modified 2025-01-31
```

La página de productos lo describe como “MGS — Marco Geográfico Seccional (Armado Nacional)” en CCL, con ENTIDAD, DISTRITO FEDERAL, DISTRITO LOCAL, MUNICIPIO y SECCION. **No se pudo extraer** porque el entorno no tiene `7z`/`py7zr`; queda como candidato para una capa nacional de un solo CRS, pendiente de validar.

### 3.6 WMS/WFS: lo que realmente responde

| Prueba | Resultado |
|---|---|
| `GET https://cartografia.ine.mx/wms/index?service=WMS&request=GetCapabilities` | **200**, WMS **1.1.1**, 43 capas bajo el grupo `Nacional` |
| CRS declarados | EPSG:4326, EPSG:3857, EPSG:900913 |
| Capas relevantes | `DISTRITO`, `DISTRITO_ANTERIOR`, `DISTRITO_LOCAL`, `MUNICIPIO`, `SECCION`, `ENTIDAD` |
| `GetMap` de `MUNICIPIO,DISTRITO` (bbox nacional, PNG) | **200**, `image/png`, 171,859 bytes |
| `GetFeatureInfo` | **Falla**: `LayerNotDefined`; todas las capas tienen `queryable="0"` |
| `GetMap` de `DISTRITO_ANTERIOR` | **Falla**: `msDrawMap(): Image handling error` / `msPostGISLayerWhichShapes(): Query error`; la capa está declarada pero no tiene extent ni datos operativos |
| `service=WFS&request=GetCapabilities` | **No hay WFS**: responde `ows:ExceptionReport`, no capabilities |
| `format=application/vnd.mapbox-vector-tile` | La petición devolvió **PNG**, no MVT; el formato aparece en capabilities pero no se comportó como vectorial en la prueba |

**Limitaciones para publicar capas nacionales WMS/WFS:**

- El WMS de INE sirve **imágenes**, no features; no hay WFS ni consulta de atributos. Para joins CCPC↔geometría hay que descargar y procesar los shapefiles.
- `DISTRITO_ANTERIOR` no es una fuente histórica utilizable en la práctica (falla el render).
- No hay capas históricas 2009/2012/2015/2018; sólo la “actual” y una “anterior” rota.
- El WMS está en 4326/3857; la cartografía fuente está en 32 UTM. Si se publica servicio propio, hay que reproyectar y simplificar.
- Sólo se probó el endpoint público; no se auditaron términos de uso, cuotas, cache ni SLA.

### 3.7 Asociación CCPC ↔ distritos

- **2024 ↔ MGS 2025:** en las **70,301 secciones comunes**, la asignación `DEF` de CCPC coincide **100.00%** con `distrito_f` de la capa `SECCION`. Es el único año que se puede unir con confianza a la cartografía actual.
- **2021 ↔ MGS 2025:** en 67,527 secciones comunes, sólo **80.62%** coincide (54,439 iguales, 13,088 distintas). No se debe unir 2021 a la cartografía 2025 sin advertirlo.
- **Cobertura de secciones:** CCPC 2024 tiene 70,751 secciones; MGS 2025 tiene 73,268; comunes 70,301. Quedan **450 secciones de CCPC sin geometría en el MGS 2025** (0.64%) y **2,967 secciones del MGS sin datos CCPC** (sin casillas/participación).
- **2009/2012:** además de las 318/221 secciones sin `DEF`, hay secciones que ya no existen en el MGS 2025 (Jalisco 2009: 143 secciones CCPC-only; CDMX: 39; Oaxaca: 57). La unión por número de sección entre años no es segura: la sección también se renumera.
- **Municipios:** las claves municipales de las muestras coinciden 100% con el MGS (JAL 125, CDMX 16, OAX 570 en 2024), pero en 2024 hay 450 secciones CCPC sin geometría y municipios nuevos (BC 006/007, Guerrero 082–085, Morelos 036, Sinaloa 019/020) que no existen en años previos.

---

## 4. Recomendación técnica

### 4.1 Granularidad

1. **Guardar CCPC en su grano nativo:** `(año, entidad, municipio, sección, sexo, edad)` con `LN, SV, NV, NS`. No agregar en la capa de almacenamiento; permite recomponer municipio, distrito y entidad sin pérdida.
2. **Municipio y sección son las granularidades seguras para series históricas.** La sección es la unidad atómica: 0 secciones con más de un `DEF` en todos los años.
3. **Distritos federales:** publicar sólo con etiqueta de plan (`DERFE 2021` o `DERFE 2023`). Para 2024 se puede agregar por sección y unir al MGS 2025. Para 2009–2021, agregar por sección al plan 2021, no presentarlo como “distrito de la elección”.
4. **No agregar distritos desde municipios.** La relación es 1:N (72 municipios partidos, hasta 5 distritos). Si se necesita un mapa municipal con distrito, usar la sección o una tabla de correspondencia oficial, nunca centroide/mayoría.

### 4.2 Identidad histórica

- **Clave de distrito versionada:** `distrito_id = entidad:numero:plan` (`09:23:DERFE2021`, `09:22:DERFE2023`). El número solo no identifica un polígono.
- **Clave municipal con vigencias:** `municipio_id = entidad:clave`, con `valid_from`/`valid_to` y `source`. Hay 19 altas 2009–2024; las claves nuevas no deben heredar historia de la clave madre.
- **No inferir existencia por ausencia:** 2012 no tiene Chiapas 117 ni Oaxaca 144/218, pero existen antes y después. Modelar `sin_dato` distinto de `0`.
- **No usar nombres como clave:** están truncados y algunos llevan comas entrecomilladas. Usar códigos normalizados.
- **`DEF` 2009–2021 es retrospectivo (marco 2021).** Etiquetar en UI y metadatos como “distrito según marco 2021”; no como “distrito histórico”. Si el producto exige el mapa contemporáneo de 2009–2018, hay que conseguir las geometrías DERFE de cada época y una correspondencia sección→distrito histórica; hoy no están en el dataset.

### 4.3 Riesgo de agregar distritos desde municipios

- **72 municipios partidos** en la cartografía 2023; **70** en CCPC 2024; **79** en CCPC 2021. Un municipio puede aportar a 2–5 distritos.
- **22.8% de los municipios comunes cambian su conjunto de distritos entre 2021 y 2024**; **19.39% de las secciones** cambian de `DEF`. Asignar el “distrito dominante” por municipio produciría errores sistemáticos y no reproducibles.
- La asignación por centroide es especialmente mala en municipios costeros, rurales dispersos y partidos por límites distritales; no se midió el error, pero la sola existencia de 72 municipios partidos lo desaconseja.
- **Regla:** si el dato es municipal, mostrarlo como municipal; si el dato es distrital, construirlo desde secciones. No “convertir” municipios a distritos sin una tabla de correspondencia y, cuando se requiera ponderar, sin área/población explícita.

### 4.4 Arquitectura de datos/geo propuesta

| Componente | Contenido mínimo |
|---|---|
| `fact_ccpc` | año, entidad, municipio, sección, sexo, edad, LN, SV, NV, NS, fuente, hash |
| `dim_entidad` | clave INE, nombre, circunscripción, vigencia |
| `dim_municipio` | entidad, clave, nombre, `valid_from`, `valid_to`, fuente |
| `dim_distrito` | entidad, número, `plan_id` (`DERFE2021`/`DERFE2023`), cabecera, `valid_from`, `valid_to` |
| `dim_seccion` | entidad, sección, municipio, `plan_id`, vigencia |
| `bridge_seccion_distrito` | entidad, sección, distrito, `plan_id`, vigencia |
| `bridge_municipio_distrito` | entidad, municipio, distrito, `plan_id`, vigencia, `es_split` |
| `geo_*` | geometría por vintage, CRS, simplificación, fuente y fecha de corte |

- Un `plan_id` explícito evita unir por accidente 2021 con 2024.
- Para servir mapas: teselas vectoriales precomputadas por capa y vintage; no recalcular overlay en cada request.
- Para WMS: usar el WMS de INE sólo como referencia visual de las capas actuales; no como API de datos (sin WFS/GetFeatureInfo). Si se necesita control de estilo y atributos, publicar servicio propio desde los shapefiles.
- Guardar `source_url`, `retrieved_at`, `last_modified`, `sha256` por artefacto.

### 4.5 Controles de calidad mínimos

- 32 archivos por año, 16 columnas, filas y hash por CSV.
- `DEF` no vacío o marcado explícito; `MPIOCVE` no vacío; `EDOCVE` 01–32; claves normalizadas.
- `LN = SV + NV + NS` al 100%; fallo bloqueante.
- Tasa de unión sección→cartografía ≥99% (2024: 99.36%; 2021: 98.13% de secciones, pero sólo 80.62% de `DEF` coincide).
- Total de distritos = 300; distribución estatal contra catálogo del plan.
- Municipios distintos contra catálogo; altas/bajas explícitas, no inferidas.
- Validación geométrica básica + topológica antes de publicar.

---

## 5. Evidencia y comandos

### Archivos principales

```
/tmp/opencode/participa-geo-national-audit/
├── ccpc_year_summary.json / .csv          # totales nacionales por año
├── ccpc_entity_year.csv                   # 192 filas: entidad-año
├── ccpc_crossyear.csv                     # comparaciones de claves y secciones
├── ccpc_district_counts_by_entity_year.csv
├── ccpc_municipality_counts_by_entity_year.csv
├── evid_ccpc_2009.json … evid_ccpc_2024.json  # detalle por entidad (incluye sec_defs y mpio_def)
├── evid_ccpc_YYYY.txt                     # diccionario original
├── carto/
│   ├── mgs_api_32.json / .csv             # 32 entidades: API, HTTP, bytes, URL
│   ├── mgs_32_inventory.json              # capas, campos, nulos, PRJ por entidad
│   ├── mgs_32_summary.csv
│   ├── inspect_samples.json               # JAL/CDMX/OAX
│   ├── shp_basic_validity.csv             # 300 distritos + 2,477 municipios
│   ├── municipio_distrito_crosscheck.csv  # 2,581 pares vs catálogo
│   └── ccpc_vs_mgs_sections.csv           # acuerdo sección→DEF 2021/2024
├── catalogos/                             # distritos, municipios, pares, secciones, cabeceras
├── wms_capabilities.xml
├── SHA256SUMS.txt
└── audit_ccpc.py, fix_oaxaca.py, inspect_carto.py, inspect_all.py, analyze_ccpc.py
```

### Comandos representativos

```bash
# Descarga y verificación CCPC
curl -sSL --retry 3 -o ccpc-2009.zip \
  https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2009.zip
unzip -t ccpc-2009.zip

# Barrido nacional (streaming, sin extraer)
python3 audit_ccpc.py 2009 2012 2015 2018 2021 2024

# Corrección Oaxaca 549 (campo entrecomillado)
python3 fix_oaxaca.py

# Cartografía: API y descarga
curl -sS "https://cartografia.ine.mx/sige8/api/bases/?producto=mgs&entidad=14&formato=Shapefile"
curl -sSL -o carto/14.zip \
  "https://storage.googleapis.com/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/14.zip"

# Inspección DBF/SHP/PRJ
python3 inspect_carto.py 14 09 20
python3 inspect_all.py

# WMS
curl -sS "https://cartografia.ine.mx/wms/index?service=WMS&request=GetCapabilities" \
  -o wms_capabilities.xml
```

### URLs de catálogo usadas

```
https://storage.googleapis.com/mapoteca/CORTE_19ENE2026_PRODUCTOSCARTOGRAFICOS/CATALOGOS/NACIONAL/3_Catálogo de Distritos Electorales Federales/ASCII/Catálogo de Distritos.txt
https://storage.googleapis.com/mapoteca/CORTE_19ENE2026_PRODUCTOSCARTOGRAFICOS/CATALOGOS/NACIONAL/6_Catálogo de Municipios/ASCII/Catálogo de Municipios.txt
https://storage.googleapis.com/mapoteca/CORTE_19ENE2026_PRODUCTOSCARTOGRAFICOS/CATALOGOS/NACIONAL/7_Catálogo de Municipios y Distritos Electorales Federales/ASCII/Catálogo de Municipios y Distritos.txt
https://storage.googleapis.com/mapoteca/CORTE_19ENE2026_PRODUCTOSCARTOGRAFICOS/CATALOGOS/NACIONAL/12_Catálogo de Secciones por Distrito Electoral Federal/ASCII/Catálogo de Secciones por Distrito.txt
https://storage.googleapis.com/mapoteca/CORTE_19ENE2026_PRODUCTOSCARTOGRAFICOS/CATALOGOS/NACIONAL/5_Catálogo de Distritos Electorales Federales Con Cabeceras Distritales/ASCII/Catálogo de Distritos Con Cabeceras Distritales.txt
```

(En la práctica se URL-encodean espacios y acentos; los archivos están en `catalogos/`.)

---

## 6. Comprobado, muestra y pendiente

| Estado | Qué |
|---|---|
| **Comprobado (barrido completo)** | 6 ZIP íntegros; 32 CSV/año; 54,872,712 filas; tamaños; hashes; municipios/distritos/secciones por año; faltantes de `DEF`/`MPIO`; duplicados; reconciliación LN; 32/32 entidades en cartografía; 300 distritos; 2,477 municipios; 73,268 secciones; 2,581 pares municipio–distrito; 72 municipios partidos; 2024 vs MGS 100% en 70,301 secciones; 2021 vs MGS 80.62%. |
| **Muestra / inspección detallada** | Campos DBF, PRJ y geometría básica capa por capa en JAL/CDMX/OAX; sin embargo, el esquema y el CRS se verificaron en las 32 entidades, y la validez básica se corrió para los 300 distritos y 2,477 municipios. |
| **Indicativo, no concluyente** | Cambios de polígono vs renumeración entre 2021 y 2024: hay 19.39% de secciones reasignadas, pero sin ambas geometrías no se puede atribuir a una cosa u otra. La comparación por número de sección entre años es indicativa porque la sección también se renumera. |
| **Pendiente** | Geometrías DERFE 2021 y anteriores; ACCDB histórico 1994–2024; validación topológica completa; nombres/cabeceras integrados; extracción del MGS nacional CCL `.7z`; 450 secciones CCPC 2024 sin geometría; términos de uso; changelog/fechas por archivo. |

---

## 7. Limitaciones explícitas

- No se auditó el MVP Jalisco ni el repositorio; no se modificó nada en `/home/arell31/participa-geo`.
- No se instalaron paquetes; la lectura DBF/SHP/PRJ y la validación geométrica son implementaciones propias, limitadas a comprobaciones básicas.
- No se dispone de GDAL/GEOS, `7z` ni `mdbtools`; por eso no se abrió el MGS nacional CCL ni el ACCDB histórico.
- El WMS se probó en un momento dado (2026-10-27); la capa `DISTRITO_ANTERIOR` puede cambiar. No se auditó su contenido interno ni su vintage.
- No se midió población/votos por municipio partido; el riesgo se sustenta en la estructura 1:N y en los cambios de asignación, no en una estimación de error electoral.
- No se verificaron licencias ni condiciones de redistribución de la cartografía INE.

---

## Apéndice A. Tabla por entidad (CCPC)

| Ent | Mpio 2009 | Mpio 2021 | Mpio 2024 | Dist. 2009 | Dist. 2021 | Dist. 2024 | Filas 2024 | DEF falt. 2009 | DEF falt. 2012 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 01 | 11 | 11 | 11 | 3 | 3 | 3 | 91,826 | 148 | 144 |
| 02 | 5 | 5 | 7 | 8 | 8 | 9 | 284,211 | 1,849 | 698 |
| 03 | 5 | 5 | 5 | 2 | 2 | 2 | 67,581 | 527 | 376 |
| 04 | 11 | 13 | 13 | 2 | 2 | 2 | 73,910 | 141 | 144 |
| 05 | 38 | 38 | 38 | 7 | 7 | 8 | 239,888 | 884 | 141 |
| 06 | 10 | 10 | 10 | 2 | 2 | 2 | 54,817 | 147 | 0 |
| 07 | 118 | 124 | 124 | 13 | 13 | 13 | 318,741 | 680 | 318 |
| 08 | 67 | 67 | 67 | 9 | 9 | 9 | 418,127 | 2,072 | 1,114 |
| 09 | 16 | 16 | 16 | 24 | 24 | 22 | 808,977 | 264 | 184 |
| 10 | 39 | 39 | 39 | 4 | 4 | 4 | 182,555 | 1,218 | 702 |
| 11 | 46 | 46 | 46 | 15 | 15 | 15 | 457,616 | 972 | 937 |
| 12 | 81 | 81 | 85 | 9 | 9 | 8 | 361,288 | 1,000 | 792 |
| 13 | 84 | 84 | 84 | 7 | 7 | 7 | 251,166 | 487 | 493 |
| 14 | 125 | 125 | 125 | 20 | 20 | 20 | 539,890 | 1,723 | 926 |
| 15 | 125 | 125 | 125 | 41 | 41 | 40 | 951,310 | 1,873 | 690 |
| 16 | 113 | 113 | 113 | 12 | 12 | 11 | 392,150 | 460 | 353 |
| 17 | 33 | 35 | 36 | 5 | 5 | 5 | 135,935 | 0 | 0 |
| 18 | 20 | 20 | 20 | 3 | 3 | 3 | 134,899 | 1,213 | 31 |
| 19 | 51 | 51 | 51 | 12 | 12 | 14 | 391,844 | 2,642 | 1,201 |
| 20 | 570 | 570 | 570 | 10 | 10 | 10 | 358,648 | 98 | 88 |
| 21 | 217 | 217 | 217 | 15 | 15 | 16 | 409,591 | 626 | 625 |
| 22 | 18 | 18 | 18 | 5 | 5 | 6 | 134,374 | 607 | 300 |
| 23 | 11 | 11 | 11 | 4 | 4 | 4 | 133,915 | 886 | 471 |
| 24 | 58 | 58 | 58 | 7 | 7 | 7 | 252,725 | 600 | 521 |
| 25 | 18 | 18 | 20 | 7 | 7 | 7 | 473,681 | 1,164 | 581 |
| 26 | 72 | 72 | 72 | 7 | 7 | 7 | 215,028 | 1,774 | 995 |
| 27 | 17 | 17 | 17 | 6 | 6 | 6 | 166,627 | 86 | 0 |
| 28 | 43 | 43 | 43 | 9 | 9 | 8 | 292,663 | 1,329 | 865 |
| 29 | 60 | 60 | 60 | 3 | 3 | 3 | 87,955 | 0 | 0 |
| 30 | 212 | 212 | 212 | 20 | 20 | 19 | 699,401 | 966 | 319 |
| 31 | 106 | 106 | 106 | 5 | 5 | 6 | 163,017 | 437 | 410 |
| 32 | 58 | 58 | 58 | 4 | 4 | 4 | 229,374 | 1,604 | 1,258 |

---
