# Reconstrucción distrital federal 2023 — estado de evidencia

**Estado: BLOCKED.** No se publica ni se calcula la serie distrital reconstruida. La única asignación sección→DERFE2023 verificada corresponde a CCPC 2024/MGS 2025; no demuestra continuidad de las secciones de 2009–2021.

## Evidencia comprobada

- La auditoría nacional (`docs/methodology/evidence/national-audit.md`, §§2.3–2.6, 3.4, 3.6, 4) encontró que 2024 concuerda 100% con MGS 2025 en las 70,301 secciones comunes. Hay 450 secciones CCPC 2024 sin geometría MGS y 2,967 secciones MGS sin dato CCPC.
- El mismo control encontró que 2021 concuerda sólo 80.62% con MGS 2025 en la asignación distrital. Los números de sección no son una llave temporal segura: las secciones cambian/renumeran.
- El catálogo histórico candidato citado por la auditoría es `HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb` (10.8 MB). La auditoría previa indicó que estaba disponible “en el bucket”, pero no dejó URL directa, objeto, hash ni copia local.
- En este checkout hay 32 ZIP MGS (`data/raw/gis/national/{01..32}.zip`) y no hay archivo `.accdb`, `.mdb` o histórico en `data/raw/`. Tampoco se encontró en `/tmp/opencode`.

## Comprobaciones reproducibles de disponibilidad

Se intentó `HEAD` sobre los dos objetos inferibles a partir de las rutas documentadas del bucket:

```text
https://storage.googleapis.com/mapoteca/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb
https://storage.googleapis.com/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb
```

Ambas devolvieron HTTP 404. La lista XML pública del bucket no está permitida: `GET https://storage.googleapis.com/mapoteca?prefix=HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025` devolvió HTTP 403. Estas rutas inferidas no se presentan como URLs oficiales del ACCDB.

La imagen disponible `participa-geo-national-api:latest` no contiene `mdb-tables` ni módulos Python `pandas_access`, `pyodbc`, `mdbtools` o `access_parser`. No se instaló nada en el host ni se obtuvo una copia del ACCDB que permitiera inspeccionarlo de forma aislada.

## Decisión y límites

No se construyó continuidad histórica por igualdad de número de sección, municipio, DEF, geometría aproximada ni proximidad. No se creó una migración de una tabla de continuidad vacía ni agregados distritales presentables: sin fuente que valide los enlaces, tales artefactos aparentarían evidencia que no existe.

En particular, quedan sin calcular y sin afirmar:

- Continuidad validada y correspondencias históricas por año.
- Cobertura con denominador LN2024 y gates 98% nacional / 95% por distrito para 2021 y 2018 (ni para los demás objetivos requeridos).
- Elegibilidad histórica de los siete números entrantes (BC09, Coahuila08, NL13/14, Puebla16, Querétaro06 y Yucatán06).
- `bridge_section_district`, `bridge_municipality_district` y `agg_municipality_district_year` históricos.

El dato disponible sí sostiene los hechos MGS autoritativos: 2,581 pares municipio–distrito y 72 municipios partidos, hasta cinco distritos por municipio. No se reemplaza esta relación N:M por asignación municipal dominante.

## Qué desbloquea el trabajo

Se requiere que INE/Mapoteca entregue la **URL directa oficial** del ACCDB citado (o un catálogo oficial descargable equivalente con identificador inequívoco por sección y vigencia), junto con confirmación de licencia/uso. Después:

1. Descargar el archivo y registrar URL, fecha, tamaño y SHA-256.
2. Inspeccionar tablas, claves, vigencias y cobertura con lector Access ejecutado en un contenedor temporal aprobado; conservar salida de inventario y el método de extracción.
3. Validar los enlaces únicos por entidad/sección entre años y hacia MGS 2025/CCPC. Toda ambigüedad debe quedar unmatched; ninguna unión se basa sólo en el número bruto.
4. Ejecutar pruebas de continuidad, reconstrucción, gates y agregación sobre los hechos reales; generar informe/CSV de cobertura por año/objetivo y distrito.
5. Sólo si pasan los gates, agregar migración, puentes y agregados distritales versionados con provenance.

Hasta completar esos pasos, N3 permanece bloqueado y no deben iniciarse N6/N9 de alcance distrital. El análisis municipal no queda bloqueado.
