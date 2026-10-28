# Task 3 — Informe de continuidad seccional y reconstrucción distrital 2023

**Estado: BLOCKED**

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
