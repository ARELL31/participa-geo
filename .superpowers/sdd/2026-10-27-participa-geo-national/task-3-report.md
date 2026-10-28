# Task 3 — Informe de continuidad seccional y reconstrucción distrital 2023

**Estado actualizado: IMPLEMENTADO; cobertura histórica insuficiente para publicación distrital.**

> La auditoría inicial registrada abajo reflejaba el estado anterior a que se proporcionara el ACCDB oficial. La sección «Reanudación» la reemplaza como conclusión vigente; se conserva el registro anterior para trazabilidad.

## Auditoría inicial (27 de octubre de 2026)

## Resultado

No se implementó la continuidad histórica ni la reconstrucción distrital. La fuente oficial histórica candidata necesaria para validar los enlaces no fue localizada/obtenida y no existe un URL oficial directo disponible en el expediente. Hacer join por número de sección violaría el requisito expreso de continuidad validada, por lo que no se sustituyó la fuente faltante por un crosswalk débil.

## Evidencia disponible y revisada

- Leídos el brief Task 3, el diseño (§§5.2, 6.1, 16.1–16.4, 16.9–16.10), el plan (Task 3 y constraints globales) y la auditoría nacional (§§2.3–2.6, 3.4, 3.6, 4).
- El repositorio contiene 32 ZIP MGS 2025 bajo `data/raw/gis/national/{01..32}.zip`; no contiene ACCDB/MDB histórico. Tampoco se halló en `/tmp/opencode`.
- La auditoría documenta 2024→MGS 2025 concordante al 100% en 70,301 secciones comunes; 450 secciones CCPC 2024 carecen de geometría MGS y 2,967 secciones MGS carecen de datos CCPC.
- La comparación 2021→MGS 2025 sólo concuerda 80.62% en secciones comunes. La misma auditoría advierte que las secciones se renumeran y que no se debe unir por número crudo.
- La única fuente candidata anotada es `HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb` (10.8 MB, según auditoría), descrita como disponible “en el bucket” pero sin URL de objeto, hash ni copia.
- `HEAD` a `https://storage.googleapis.com/mapoteca/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb` y al mismo nombre bajo `MGS_UTM_SHAPEFILE_15DIC2025/` dio HTTP 404 en ambos casos. El listado `https://storage.googleapis.com/mapoteca?prefix=HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025` dio HTTP 403. Son intentos de localización, no URLs oficiales del archivo.
- La imagen `participa-geo-national-api:latest` no trae `mdb-tables` ni módulos `pandas_access`, `pyodbc`, `mdbtools`, `access_parser`. No se instalaron paquetes en el host.
- La evidencia disponible sí confirma MGS con 2,581 pares municipio–distrito y 72 municipios partidos (hasta cinco distritos). No se asignó un distrito único a municipios.

## Bloqueo exacto y acción requerida

Falta la **URL directa oficial de descarga** (o catálogo INE equivalente, descargable y con identificador/vigencia inequívocos por sección) del ACCDB `HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb`. Además, se requiere confirmación de licencia/uso. Las dos URLs inferidas arriba no son el objeto (404), y el bucket no permite listar objetos (403), por lo que no es posible confirmar ni obtener la fuente a partir de este entorno.

Desbloquea: que INE/Mapoteca proporcione el URL exacto del objeto o publique el catálogo equivalente. Con ello se descargará en el entorno aislado, se registrará URL/fecha/tamaño/SHA-256, se inspeccionará con herramienta Access dentro de contenedor y se validarán enlaces y cobertura antes de generar migración/tablas y agregados.

## Trabajo no realizado por seguridad metodológica

No se creó `ingestion/continuity.py`, `pipelines/validation/continuity.py`, migración `0006`, CLI de reconstrucción ni agregados/puentes distritales; no hay datos validados para poblarlos y una interfaz que sugiriera reconstrucción disponible sería engañosa. No se calcularon cobertura 2021/2018, numerador LN2024 mapeado, gates nacionales/distritales, ni elegibilidad de los siete números nuevos. Por tanto no se ejecutaron pruebas RED/GREEN específicas ni informe de cobertura sobre datos reales; no es posible afirmar 2024 exacto por código, unmatched no imputado, agregación distrital sumable ni cumplimiento 98%/95%.

La metodología y la evidencia reproducible quedan en `docs/methodology/national-district-reconstruction.md`. N3 queda bloqueado; N6/N9 distritales no deben comenzar. El trabajo municipal puede continuar.

## Verificación y commit

- Test summary: no se ejecutó una suite de Task 3, ya que la fuente de continuidad requerida no está disponible y el entregable se detuvo en el gate BLOCKED.
- Se registraron solamente documentación/informe de Task 3; ningún artefacto de datos fue agregado al repositorio.

## Reanudación — fuente oficial disponible

**Resultado vigente:** se implementaron continuidad oficial por sección, validación DERFE2023, migración `0006`, bridges, agregados y cobertura real. No se publica reconstrucción distrital histórica para 2009–2021, porque los cinco años fallan el gate nacional de 98%; todos sus distritos quedan en estado efectivo `insufficient`. El 2024 de referencia pasa exacto al 100%.

### Fuente, exportación y selección del plan

- ACCDB oficial: `https://storage.googleapis.com/mapoteca/historicos/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb`, local en `data/raw/continuity/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb`; 10,797,056 bytes; SHA-256 `f88804f66fa0bcfc855159a1c2332be06f283bd697e2a037e8a70db3fc5934aa`.
- Inspección/extracción con `mdbtools` dentro del contenedor Debian temporal; tabla `HISTORICO_SECC_ELECT_PEF1994-PEF2024_CORTE_diciembre2025`. Script reproducible: `scripts/export_official_section_history.sh`. El CSV exportado tiene 75,895 filas, SHA-256 `e91f0f6199a8efeaf755fcc9a4c08e705bc15508d060398b627876582af6f5cb`; la aplicación no necesita mdbtools.
- Se eligió `Nueva_Dttacion_2023` como referencia explícita del plan DERFE2023. En las 70,301 secciones comunes, no tuvo discrepancias contra CCPC 2024 `DEF` ni MGS `SECCION.distrito_f`. Concuerda también con `Distrito_PEF2024` en los 73,716 valores poblados, pero no con revisiones de 2024/2025 posteriores en todos sus registros.
- El archivo oficial no expresa una licencia específica; ACCDB/CSV se dejan ignorados por Git. Confirmar condiciones de redistribución con INE antes de compartir la fuente bruta.
- Catálogo de cabeceras: `data/raw/continuity/district-headquarters.txt`, SHA-256 `c244b4ed3e55c668a4a8fde4a8f5999fa95d8974b6a45a5ef91660a5c1a4fb47`.

### Regla y resultados de cobertura

Los vínculos exigen la fila/columna oficial de origen del año solicitado, destino DERFE2023 y acuerdo de distrito con MGS. No se usa el número crudo para inferir continuidad. Las bajas parciales y destinos no singulares/ambiguos quedan `unmatched`; únicamente se aceptan fusiones completas con destino explícito único, presente y validado. El denominador de cobertura es LN 2024. Se exige 98% nacional y 95% distrital; fallar el gate nacional hace insuficientes todas las filas distritales del año.

| Año | Matched / unmatched | LN2024 cubierto | Nacional ≥98% | Distritos que pasan 95% local | Elegibles efectivos |
|---|---:|---:|---|---:|---:|
| 2009 | 62,590 / 2,344 | 82.5931% | No | 83 | 0 |
| 2012 | 63,326 / 2,273 | 83.8598% | No | 71 | 0 |
| 2015 | 66,282 / 2,080 | 86.5857% | No | 90 | 0 |
| 2018 | 66,313 / 2,095 | 86.6237% | No | 90 | 0 |
| 2021 | 66,959 / 1,853 | 89.0089% | No | 110 | 0 |
| 2024 | 70,751 / 0 | 100.0000% | Sí | 300 | 300 |

Los siete números distritales entrantes (BC09, Coahuila08, NL13/14, Puebla16, Querétaro06, Yucatán06) no heredan identidades por número; las siete áreas quedan insuficientes para 2009–2021. Puebla16 supera localmente 95% en 2021 (96.9523%), pero no es elegible porque ese año falla el gate nacional.

MGS contiene 73,268 secciones y su bridge reproduce 2,581 pares municipio–distrito, 72 municipios divididos y máximo cinco distritos por municipio. Hay 450 secciones CCPC 2024 sin geometría MGS y 2,967 secciones MGS sin dato CCPC; ambos listados se exportan y permanecen sin imputar cuando corresponde.

### Implementación y verificación

- Añadidos `alembic/versions/0006_continuity.py`, lógica de dominio, pipeline/CLI `continuity build` y `district rebuild`, tests unitarios e integración de artefactos. No se modificaron migraciones 0001–0005; no se agregó modelo/API/UI distrital.
- Artefactos ignorados por Git en `data/processed/national/continuity/`: reportes CSV por año, cobertura, bridges, agregados, observaciones, unmatched/no-geometry y manifiesto de hashes.
- Base local después del build: 406,866 vínculos de continuidad, 73,268 filas de bridge sección-distrito, 2,581 pares municipio-distrito, 15,428 agregados; todos satisfacen `LN = SV + NV + NS`, sin mezcla de plan (todos `DERFE2023`).
- Tests unitarios y de artefactos: 17 passed. Migración integrada con Postgres: 2 passed (ejecutada separadamente en la red Docker `participa-geo-national_internal`). Ruff y `git diff --check`: sin errores. Advertencia no bloqueante deprecada de Starlette/httpx.
- Informe metodológico completo y reproducible: `docs/methodology/national-district-reconstruction.md`.

**Commit:** pendiente al momento de esta actualización; no se hizo push.
