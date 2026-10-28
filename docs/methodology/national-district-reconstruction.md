# Reconstrucción distrital federal 2023 — estado de evidencia

**Estado: implementado; ningún año 2009–2024 pasa la compuerta nacional de 98%.** La cobertura corregida exige que las secciones CCPC tengan geometría MGS. 2009–2021 y 2024 quedan `insufficient`; 2024 alcanza 95.1334%, no 100%.

## Fuente oficial incorporada y decisión de plan

- ACCDB: `data/raw/continuity/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb`, descargado del URL oficial `https://storage.googleapis.com/mapoteca/historicos/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb`; tamaño 10,797,056 bytes; SHA-256 `f88804f66fa0bcfc855159a1c2332be06f283bd697e2a037e8a70db3fc5934aa`.
- Tabla inspeccionada dentro de Debian temporal con `mdbtools`: `HISTORICO_SECC_ELECT_PEF1994-PEF2024_CORTE_diciembre2025`. Exportación reproducible: `scripts/export_official_section_history.sh`; CSV `data/raw/continuity/official-section-history.csv`, 75,895 registros y SHA-256 `e91f0f6199a8efeaf755fcc9a4c08e705bc15508d060398b627876582af6f5cb`. El runtime usa este CSV validado, no requiere Access ni mdbtools.
- Se seleccionó `Nueva_Dttacion_2023` como referencia DERFE2023: en las 70,301 secciones comunes a historia, CCPC 2024 y MGS 2025 no hay discrepancias con CCPC `DEF` ni con `SECCION.distrito_f`. También concuerda con `Distrito_PEF2024` en sus 73,716 registros poblados, pero el nombre seleccionado identifica explícitamente el plan 2023. Los campos de julio 2024/PEPJF2025 y diciembre 2025 no son intercambiables (1,060 y 3,413 diferencias contra el campo elegido, respectivamente, entre sus registros poblados).
- MGS conserva 73,268 secciones, 2,581 pares municipio–distrito, 72 municipios divididos y máximo cinco distritos por municipio. Catálogo oficial de cabeceras: `data/raw/continuity/district-headquarters.txt`, SHA-256 `c244b4ed3e55c668a4a8fde4a8f5999fa95d8974b6a45a5ef91660a5c1a4fb47`.
- El objeto no incluye una declaración de licencia específica. El ACCDB y el CSV permanecen fuera de Git; antes de redistribuir los archivos fuente debe confirmarse su licencia/uso con INE. Este trabajo registra hashes y deriva resultados auditables, no publica esos archivos.

## Regla de continuidad y cobertura

Cada vínculo histórico exige sección fuente presente en la columna oficial de su año (`Distrito_PEF2009/2012/2015/2018/2021`), destino oficial DERFE2023, acuerdo del distrito objetivo con MGS y ausencia de baja/reseccionamiento parcial. Se acepta además una fusión completa sólo si la nota oficial especifica un destino singular existente y coherente con el catálogo/MGS. Altas, bajas, movimientos parciales y destinos ambiguos no se completan por número: quedan `unmatched`. En el material histórico CCPC, `DEF` es el campo de plan 2021, no se reasigna como una identidad de los planes anteriores.

El denominador es LN agregado por sección del CCPC 2024; el numerador es LN de secciones con continuidad validada hacia el plan DERFE2023. Para reconstrucción publicable se requiere ≥98% nacional y ≥95% en cada distrito. El gate nacional se aplica también al estado efectivo distrital; se informan aparte los distritos que localmente llegan a 95%.

| Año origen | Vínculos matched / unmatched | Cobertura LN2024 | Gate nacional | Distritos ≥95% localmente | Distritos efectivos elegibles |
|---|---:|---:|---|---:|---:|
| 2009 | 62,590 / 2,344 | 82.5931% | insuficiente | 83 | 0 |
| 2012 | 63,326 / 2,273 | 83.8598% | insuficiente | 71 | 0 |
| 2015 | 66,282 / 2,080 | 86.5857% | insuficiente | 90 | 0 |
| 2018 | 66,313 / 2,095 | 86.6237% | insuficiente | 90 | 0 |
| 2021 | 66,959 / 1,853 | 89.0089% | insuficiente | 110 | 0 |
| 2024 | 70,301 / 450 | 95.1334% | insuficiente | 191 | 0 |

La cobertura usa las 70,751 secciones y 98,330,348 LN del CCPC2024 como denominador. Sólo las 70,301 que también están en MGS y coinciden con el catálogo oficial contribuyen al numerador: 93,545,034 LN. Las 450 sin geometría MGS quedan unmatched, retienen 4,785,314 LN en denominador y aportan cero al numerador. Por distrito, el gate usa el mismo numerador restringido a secciones MGS validadas y el denominador CCPC2024 del distrito.

MGS contiene 2,967 secciones sin hecho CCPC2024. No se les inventa LN: `coverage-report.csv` reporta por distrito/nación su `mgs_only_section_count`, `mgs_only_ln=0` (ningún LN observado) y `section_universe_gap_count`; el listado `mgs-sections-without-2024-ccpc.csv` marca cada fila `uncovered_no_ccpc_ln`, `section_count=1`, LN vacío y `ln_status=absent_no_ccpc_fact`. El hueco total de universo es 3,417 secciones (450 CCPC-sin-MGS + 2,967 MGS-sin-CCPC). `ccpc-2024-sections-without-mgs.csv` lista por separado las 450 secciones con su LN conocido. La auditoría común de plan sigue teniendo 70,301 secciones sin discrepancias; eso no convierte las secciones fuera de MGS en geometría cubierta.

Los siete distritos con números entrantes (BC09, Coahuila08, NL13/14, Puebla16, Querétaro06 y Yucatán06) se evalúan en el plan DERFE2023, sin heredar identidades por semejanza numérica. Ninguno se vuelve históricamente elegible: cada año 2009–2021 falla el gate nacional. Puebla16 alcanza 96.9523% local en 2021, pero su estatus efectivo sigue siendo `insufficient` por el gate nacional; los demás casos no alcanzan 95% local en esos años.

## Implementación y artefactos

- Migraciones aditivas `0006_continuity.py`, `0007_coverage_gap_audit.py` y `0008_total_section_gap.py`; no se editaron `0001`–`0005`. La cobertura persiste LN, conteos CCPC/MGS y el gap total de secciones junto con los gates.
- Comandos `continuity build` y `district rebuild`; validación en `apps/api/participa_geo/ingestion/continuity.py` y `pipelines/validation/continuity.py`.
- Artefactos reproducibles bajo `data/processed/national/continuity/`: continuidad por año, reporte de cobertura, ambos puentes, observaciones distritales, agregados municipio×distrito×año, listas unmatched/no-geometry y `continuity-build.json`.
- Base real: 73,268 filas puente sección-distrito, 2,581 intersecciones municipio-distrito, 15,428 agregados; todos los agregados reconcilian `LN = SV + NV + NS` y se etiquetan `DERFE2023`. Los estatus históricos permanecen insuficientes; no hay modelo/API/UI distrital.

## Auditoría bloqueada inicial — SUPERSEDIDA (no es el estado vigente)

> Este registro describe únicamente el checkout anterior a la entrega del ACCDB. Sus conclusiones de bloqueo, ausencia de implementación y acciones pendientes fueron reemplazadas primero por la reanudación y luego corregidas en «Fix round 1» del informe Task 3. No usar este bloque como resultado actual.

### Evidencia que se revisó en la auditoría inicial

- La auditoría nacional (`docs/methodology/evidence/national-audit.md`, §§2.3–2.6, 3.4, 3.6, 4) encontró que 2024 concuerda 100% con MGS 2025 en las 70,301 secciones comunes. Hay 450 secciones CCPC 2024 sin geometría MGS y 2,967 secciones MGS sin dato CCPC.
- El mismo control encontró que 2021 concuerda sólo 80.62% con MGS 2025 en la asignación distrital. Los números de sección no son una llave temporal segura: las secciones cambian/renumeran.
- El catálogo histórico candidato citado por la auditoría es `HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb` (10.8 MB). La auditoría previa indicó que estaba disponible “en el bucket”, pero no dejó URL directa, objeto, hash ni copia local.
- En este checkout hay 32 ZIP MGS (`data/raw/gis/national/{01..32}.zip`) y no hay archivo `.accdb`, `.mdb` o histórico en `data/raw/`. Tampoco se encontró en `/tmp/opencode`.

### Comprobaciones reproducibles de disponibilidad inicial

Se intentó `HEAD` sobre los dos objetos inferibles a partir de las rutas documentadas del bucket:

```text
https://storage.googleapis.com/mapoteca/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb
https://storage.googleapis.com/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb
```

Ambas devolvieron HTTP 404. La lista XML pública del bucket no está permitida: `GET https://storage.googleapis.com/mapoteca?prefix=HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025` devolvió HTTP 403. Estas rutas inferidas no se presentan como URLs oficiales del ACCDB.

La imagen disponible `participa-geo-national-api:latest` no contiene `mdb-tables` ni módulos Python `pandas_access`, `pyodbc`, `mdbtools` o `access_parser`. No se instaló nada en el host ni se obtuvo una copia del ACCDB que permitiera inspeccionarlo de forma aislada.

### Decisión y límites en ese corte inicial

No se construyó continuidad histórica por igualdad de número de sección, municipio, DEF, geometría aproximada ni proximidad. No se creó una migración de una tabla de continuidad vacía ni agregados distritales presentables: sin fuente que valide los enlaces, tales artefactos aparentarían evidencia que no existe.

En particular, quedan sin calcular y sin afirmar:

- Continuidad validada y correspondencias históricas por año.
- Cobertura con denominador LN2024 y gates 98% nacional / 95% por distrito para 2021 y 2018 (ni para los demás objetivos requeridos).
- Elegibilidad histórica de los siete números entrantes (BC09, Coahuila08, NL13/14, Puebla16, Querétaro06 y Yucatán06).
- `bridge_section_district`, `bridge_municipality_district` y `agg_municipality_district_year` históricos.

El dato disponible sí sostiene los hechos MGS autoritativos: 2,581 pares municipio–distrito y 72 municipios partidos, hasta cinco distritos por municipio. No se reemplaza esta relación N:M por asignación municipal dominante.

### Qué se requería en ese corte inicial

Se requiere que INE/Mapoteca entregue la **URL directa oficial** del ACCDB citado (o un catálogo oficial descargable equivalente con identificador inequívoco por sección y vigencia), junto con confirmación de licencia/uso. Después:

1. Descargar el archivo y registrar URL, fecha, tamaño y SHA-256.
2. Inspeccionar tablas, claves, vigencias y cobertura con lector Access ejecutado en un contenedor temporal aprobado; conservar salida de inventario y el método de extracción.
3. Validar los enlaces únicos por entidad/sección entre años y hacia MGS 2025/CCPC. Toda ambigüedad debe quedar unmatched; ninguna unión se basa sólo en el número bruto.
4. Ejecutar pruebas de continuidad, reconstrucción, gates y agregación sobre los hechos reales; generar informe/CSV de cobertura por año/objetivo y distrito.
5. Sólo si pasan los gates, agregar migración, puentes y agregados distritales versionados con provenance.

Esas frases describen el corte inicial y están supersedidas por el trabajo y cobertura real documentados arriba.
