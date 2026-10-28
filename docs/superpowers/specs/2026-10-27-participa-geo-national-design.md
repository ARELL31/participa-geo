# PARTICIPA-GEO Nacional — Diseño de expansión municipal y distrital

Fecha: 2026-10-27. Estado: **aprobado por el usuario; ejecución nacional autorizada**. Método: agentes con ChatGPT Luna; respaldo Gemini 3.8 Flash si se agotan los tokens.

## 1. Intención

Convertir el piloto verificado de Jalisco en una plataforma nacional de inteligencia territorial de participación y abstención, con dos unidades de análisis seleccionables por el usuario:

- **Municipio**
- **Distrito electoral federal**

La persona usuaria podrá cambiar de nivel, entidad y territorio sin que la plataforma confunda una unidad con otra. El objetivo sigue siendo institucional: identificar riesgos, comparar escenarios hipotéticos y priorizar acciones preventivas con evidencia, no perfilar personas ni prometer efectos causales.

El enfoque A fue aprobado en conversación: **modelos separados para municipio y distrito; el distrito no se obtiene promediando municipios**. La alternativa jerárquica conjunta queda como evolución posterior.

## 2. Evidencia de la auditoría nacional

Se auditaron los seis ZIP CCPC completos y la cartografía MGS de las 32 entidades. Evidencia durable:

- `docs/methodology/evidence/national-audit.md`
- `docs/methodology/evidence/national/ccpc_year_summary.csv`
- `docs/methodology/evidence/national/ccpc_entity_year.csv`
- `docs/methodology/evidence/national/ccpc_crossyear.csv`
- `docs/methodology/evidence/national/mgs_32_summary.csv`
- `docs/methodology/evidence/national/mgs_api_32.csv`
- `docs/methodology/evidence/national/municipio_distrito_crosscheck.csv`
- `docs/methodology/evidence/national/shp_basic_validity.csv`

Hechos comprobados:

| Hecho | Resultado |
|---|---|
| ZIP CCPC | 6 años, 32 CSV/año, 54,872,712 filas, 292.5 MB comprimidos / 3.73 GB descomprimidos |
| Conciliación | `LN = SV + NV + NS` en 100% de las filas |
| Cobertura | 32 entidades en todos los años; 2,458→2,477 municipios; 300 distritos federales |
| Cartografía | 32/32 entidades HTTP 200; 2,477 municipios, 300 distritos federales, 679 locales, 73,268 secciones |
| Relación municipio–distrito | 2,581 pares exactos; 72 municipios partidos entre 2 y 5 distritos |
| Geografía distrital | 2009–2021 usa DERFE 2021; 2024 usa DERFE 2023 |
| Cambio 2021→2024 | 13,183/67,976 secciones comunes cambian de distrito (19.39%); 7 claves salen, 7 entran |
| Calidad | 0 duplicados analíticos, 0 `MPIOCVE` vacío, 0 `EDOCVE` inválido |
| Faltantes | 28,477 filas/318 secciones sin `DEF` en 2009; 15,677/221 en 2012; secciones obsoletas, no imputar |
| Municipios | 2012 sin Chiapas 117 ni Oaxaca 144/218; no convertir ausencia en cero |
| Cartografía WMS INE | WMS funciona para DISTRITO/MUNICIPIO; no hay WFS; `GetFeatureInfo` falla; `DISTRITO_ANTERIOR` no es utilizable |

Consecuencias que el diseño debe respetar:

1. La llave de distrito **no es una identidad geográfica estable**. Debe incluir el plan: `(entidad, número, DERFE2021|DERFE2023)`.
2. Un municipio puede pertenecer a varios distritos. No existe una jerarquía municipio→distrito.
3. La sección es la unidad atómica de agregación: una sección pertenece a un solo distrito dentro de cada plan.
4. La ausencia de dato no es cero. Las secciones sin `DEF`, los municipios ausentes y los territorios nuevos deben quedar como insuficientes o sin distrito, no imputarse.
5. El WMS público del INE no sirve como API de atributos; la plataforma publicará sus propias capas desde PostGIS/GeoServer.

## 3. Objetivos, no objetivos y condiciones de fracaso

### Objetivos

- Cobertura de las 32 entidades, 2,477 municipios y 300 distritos federales.
- Historia 2009–2024 con denominadores y calidad auditables.
- Selector global Municipio/Distrito federal y filtros por entidad.
- Modelo municipal y modelo distrital separados, evaluados temporalmente.
- Escenarios A/B por nivel, sin mezclar unidades.
- Mapa nacional eficiente y perfiles territoriales.
- Reportes y exportaciones por nivel, entidad y territorio.
- Trazabilidad de dataset, plan distrital, modelo y supuestos.

### No objetivos de la primera versión nacional

- Distritos electorales locales (los 679 de la cartografía quedan fuera).
- Resultados por casilla, partido o candidatura.
- Inferencia sobre personas.
- Un modelo jerárquico conjunto municipio–distrito.
- Predicciones para todos los distritos si la reconstrucción histórica no supera el umbral de cobertura.
- Autenticación, perfiles de usuario, campañas o optimización partidista.
- Publicación abierta de datos crudos o cartografía sin revisión de condiciones.

### Condiciones de fracaso

- Presentar el distrito 2021 y el 2023 como la misma serie.
- Asignar un distrito dominante a un municipio partido.
- Rellenar secciones sin `DEF` o municipios ausentes con cero.
- Publicar un distrito sin suficiente historia como si tuviera riesgo comparable.
- Entrenar con datos posteriores al objetivo o reutilizar un `model_run_id` con cohortes distintas.
- Mostrar un mapa nacional cargando las 2,477 geometrías completas en el navegador.
- Declarar cobertura nacional cuando alguna entidad o nivel no se haya verificado.

## 4. Enfoques considerados

### A. Dos modelos independientes, grano sección y capas nacionales — **elegido**

El CCPC se almacena en su grano nativo de sección; se agrega a municipio y distrito por separado. El distrito usa el plan 2023 y una reconstrucción histórica por sección, con umbral de cobertura. Dos modelos, dos cohortes, dos explicaciones.

Ventajas: rigor, trazabilidad, reutiliza el stack, permite corregir agregaciones. Costes: ETL nacional, doble validación, reconstrucción distrital y mayor volumen.

### B. Modelo municipal y distrito como agregación de predicciones municipales — rechazado

Rápido, pero un distrito no es la suma de municipios y 72 municipios están partidos. Produciría una falsa sensación de precisión.

### C. Modelo jerárquico multinivel conjunto — evolución posterior

Más elegante para pooling estado/distrito/municipio, pero añade complejidad de inferencia, explicación y validación. No es necesario para la primera versión nacional.

## 5. Arquitectura

Se conserva el monorepositorio y el monolito modular FastAPI. No se introducen microservicios, colas ni Kubernetes.

```text
apps/web/                 React, TypeScript, MapLibre, TanStack Query
apps/api/participa_geo/   API, dominio, modelos, reportes
pipelines/                ingestión, reconstrucción distrital, entrenamiento
gis/geoserver/            publicación y seguridad
data/raw/                 ZIP oficiales (ignorados por Git)
data/processed/           agregados/artefactos (ignorados por Git)
docs/                     arquitectura, metodología, evidencias, decisiones
tests/                    unitarias, contratos, integración, E2E
compose.yaml
```

### Servicios

- `db`: PostgreSQL/PostGIS; datos nativos, agregados, geometrías y resultados.
- `geoserver`: WMS/WFS propios por nivel y plan; sin administración pública.
- `api`: lecturas, escenarios, reportes y gateway GIS.
- `web`: shell y visualizaciones.

### 5.1 Capas de datos

| Capa | Responsabilidad |
|---|---|
| `raw` | ZIP/CSV oficiales, hash, URL, fecha de descarga; no se sirve por API |
| `fact_ccpc_section` | grano nativo: año, entidad, municipio, sección, sexo, edad, LN/SV/NV/NS, plan(es) y versión de dataset; particionada por año |
| `agg_territory_year` | agregados municipales y distritales; única fuente de la API |
| `dim_entidad` | 32 entidades, circunscripción, vigencia |
| `dim_municipio` | entidad+clave, nombre, vigencias, fuente |
| `dim_distrito` | entidad+número+plan, cabecera/etiqueta, vigencia |
| `bridge_section_district` | sección→distrito por plan, evidencia y cobertura |
| `bridge_municipality_district` | pares derivados de secciones, con conteo/LN y `is_split`; nunca asignación 1:1 |
| `geo_*` | geometrías municipales/distritales por plan, CRS y corte |
| `model_run`/`prediction` | nivel, plan, cohorte, artefactos y resultados |
| `scenario`/`scenario_result` | selección, supuestos y A/B por nivel |

`fact_ccpc_section` es internal/analítica; la API sólo expone agregados. No hay datos personales, sólo celdas agregadas por sección, sexo y edad.

### 5.2 Ingreso y reconstrucción distrital

1. Descargar y verificar los seis ZIP; registrar URL, SHA-256, `Last-Modified` y fecha de descarga.
2. Leer cada CSV con parser formal (Oaxaca contiene nombres entre comillas y comas). Normalizar `EDOCVE` a 2 dígitos, `MPIOCVE` a 3, `DEF` a 2; conservar el valor original y el normalizado.
3. Validar esquema, tipos, `LN=SV+NV+NS`, claves, rangos y duplicados. Fallar el lote antes de escribir.
4. Insertar `fact_ccpc_section` en una transacción por entidad/año o por lote particionado; `COPY`/streaming, nunca cargar 3.7 GB en memoria.
5. Agregar a municipio sumando conteos; calcular shares de edad y ruralidad desde `LN`, nunca desde votos.
6. Agregar a distrito por sección. Para 2024, `DEF` corresponde a `DERFE2023`; para 2009–2021, `DEF` corresponde a `DERFE2021`.
7. Construir la **serie analítica de distritos 2023**: cada sección histórica se asigna al distrito 2023 usando el mapa sección→distrito de 2024. Las secciones sin correspondencia se marcan `unmatched`; no se imputan. La serie se etiqueta “reconstruida por sección”.
8. Calcular cobertura de reconstrucción por año: `LN de secciones mapeadas / LN total`. Umbral nacional mínimo: **98% de LN**. Si un año no alcanza, el modelo distrital de ese año no se publica.
9. Calcular cobertura por distrito: proporción de la LN reconstruida que pudo asignarse. Un distrito con menos del **95%** de su LN reconstruida, o sin las observaciones requeridas, queda `insufficient`.
10. Conservar los agregados oficiales del plan 2021 en una tabla de auditoría; no se publican como si fueran el plan 2023 ni se mezclan con este.

La reconstrucción no es un resultado oficial del INE. Se mostrará como “Distrito federal, marco 2023, historia reconstruida por sección” y tendrá una nota metodológica.

### 5.3 Geometrías

- Descargar los 32 MGS (167 MB). Cada entidad viene en UTM 11N–16N; transformar **realmente** a EPSG:4326, no reetiquetar.
- Cargar `ENTIDAD`, `MUNICIPIO`, `DISTRITO_FEDERAL` y `SECCION`; validar vacíos, anillos y límites.
- Publicar sólo las capas municipales y distritales del plan 2023, más entidades. La capa 2021 no se publica sin geometría oficial validada; queda como tabla de auditoría.
- Etiquetar distritos como “Distrito {número:02d} — {cabecera}” usando el catálogo de cabeceras; nunca inventar un nombre.
- Simplificar geometrías para la vista nacional y conservar una versión de detalle para la ficha/exportación. Documentar tolerancias.
- GeoServer publica WMS nacional y WFS filtrado por entidad/bbox. No se descarga el país completo en el navegador.

## 6. Modelos

### 6.1 Cohortes

Para cada nivel y año objetivo `t`:

- identidad `verified_catalogue` y huella `not_verified` como mínimo;
- calidad `SV+NV>=1000` y `NS/LN<=0.10` en `t`, `t-3`, `t-6` (retrospectivas) o en `2021/2024` (2027);
- observaciones completas en los años requeridos;
- para distrito, reconstrucción 2023 con cobertura suficiente.

Las exclusiones se reportan por año y nivel. Municipios/distritos nuevos sin historia quedan insuficientes; no heredan la serie de una clave madre.

### 6.2 Modelo M0 y M1

M0: abstención conocida del mismo tipo de elección en `t-6`.

M1: `StandardScaler` + `Ridge(alpha=1.0)` con:

1. `same_type_abstention_pct` (t-6)
2. `previous_abstention_pct` (t-3)
3. `previous_young_share` (LN 18–29, t-3)
4. `previous_senior_share` (LN 60+, t-3)
5. `previous_rural_share` (secciones rurales, t-3)
6. `is_midterm`
7. efectos fijos de entidad (one-hot; la entidad de referencia se documenta)

Los efectos fijos permiten comparar entidades sin promediar tasas. No se usa voto ni composición de votantes en los predictores; los shares se calculan sobre LN.

### 6.3 Validación y selección

| Nivel | Entrenamiento | Validación | Prueba |
|---|---|---|---|
| Municipal | objetivos 2015/2018 | 2021 | 2024 |
| Distrital (plan 2023 reconstruido) | objetivos 2015/2018 | 2021 | 2024 |

- Se elige M1 sólo si reduce MAE municipal/distrital en 2021; empate mantiene M0.
- La prueba 2024 se calcula después de congelar familia, variables, alpha y umbrales.
- Ajuste final para 2027 con 2015/2018/2021/2024.
- Si el modelo distrital no alcanza cobertura o no tiene suficientes observaciones de error, no se publica banda ni clasificación con apariencia de certeza.

Métricas: MAE, RMSE, sesgo, MAE ponderado por LN conocida, cobertura y exclusiones por nivel. Se publican M0 y M1 aunque M0 gane.

### 6.4 Incertidumbre y semáforo

- Banda por nivel: P90 del error absoluto de 2021 de la familia elegida; mínimo 30 errores.
- Cobertura empírica contra 2024; no llamarla intervalo de confianza del 90%.
- Semáforo: bajo <40%, medio 40–<50%, alto >=50%, insuficiente si no elegible.
- Inestabilidad si la banda cruza un umbral; mostrar rango y texto, no sólo color.
- No se fuerza consistencia municipio↔distrito; se advierte que son modelos separados.

### 6.5 Identidad del modelo

`model_run_id` incluye nivel, plan distrital, hash de datos, estados de identidad, cohortes/exclusiones, parámetros/coeficientes de M0/M1, métricas y versión de features. Cambiar cualquier evidencia cambia el ID. La carga de un modelo conserva predicciones y escenarios trazables.

## 7. API

Prefijo `/api/v1`; cambios aditivos salvo donde el contrato nacional exige nuevos campos. OpenAPI genera tipos TypeScript.

### Filtros comunes

- `level`: `municipality` | `federal_district`
- `state_code`: 01–32 (opcional para resumen nacional)
- `territory_id`: UUID
- `year`: 2009/2012/2015/2018/2021/2024
- `target_year`: 2027
- `page`, `page_size`; máximo 500 en listas nacionales.

### Rutas

| Ruta | Contrato nacional |
|---|---|
| GET `/territories` | `level`, `state_code?`, `q`, paginación; devuelve ID, nivel, entidad, código, nombre, plan, estados |
| GET `/participation/history` | `level`, `territory_id?`, `year?`, `state_code?`; agregado estatal/nacional cuando no hay territorio |
| GET `/participation/summary` | resumen por entidad/nivel para el panel nacional; una fila por entidad |
| GET `/models` | modelos por nivel/plan, métricas M0/M1, cobertura, limitaciones |
| GET `/predictions` | `level`, `model_run_id`, `target_year=2027`, `territory_id?`, `state_code?`; 2,477/300 resultados paginados |
| POST `/scenarios` | `level` inferido del modelo; IDs del mismo nivel; máximo 1,000 municipios o 300 distritos; sin texto libre |
| GET `/scenarios/{id}` | resultado persistido; no recalcula |
| GET `/recommendations` | reglas por nivel; explicaciones y prioridades |
| POST `/reports` | exportaciones por nivel/entidad; límites nacionales |
| GET `/gis/wms` | capas municipales/distritales/entidades; WMS nacional |
| GET `/gis/wfs` | sólo por entidad/bbox, máximo 1,000 features; sin CQL/Transaction/REST/URLs |

- Escenarios: `territory_ids` deben ser del mismo nivel y del plan del modelo; rechazar mezcla municipio/distrito.
- Reportes: CSV/XLSX hasta 20,000 filas; GeoJSON por entidad/nivel; PDF nacional/metodológico y fichas; no generar 32 PDFs automáticamente.
- Errores `application/problem+json`; límites `ProblemDetail`; sin datos personales.

## 8. Interfaz

- Shell existente con selector global **Nivel: Municipio / Distrito federal**.
- Selector de entidad; búsqueda por nombre/código; selector de territorio dependiente del nivel.
- Panel nacional: mapa de entidades y tabla de 32 resúmenes; al elegir entidad, mapa municipal o distrital.
- Ficha municipal: historia, predicción, escenario, distritos con los que se cruza (participación por sección), advertencia de que no es una jerarquía.
- Ficha distrital: historia reconstruida 2023, municipios/secciones que lo componen, predicción si elegible, advertencia de plan.
- Mapa: WMS nacional; WFS sólo al seleccionar entidad o bbox; tabla alternativa; sin 2,477 features en una sola respuesta.
- Filtros en URL: `level`, `state`, `territory_id`, `year`; `target_year=2027` separado.
- Colores y componentes del design system; estados de insuficiencia textuales; foco visible; 320/375/1440; sin depender del color.
- La etiqueta de distrito incluye plan: “Distrito 05 · marco 2023”.
- La historia distrital reconstruida se marca visualmente; no se muestra como observación oficial.

## 9. Reportes y exportaciones

- Metodología nacional y presentación ejecutiva.
- Fichas por entidad, municipio o distrito elegido; no un informe de 2,477 fichas.
- CSV/XLSX nacional con observaciones, features, exclusiones y diccionario.
- GeoJSON por entidad/nivel; mapas A/B con referencia 2023 y leyenda común.
- CSVs crudos oficiales sólo en el ZIP técnico con confirmación de licencia.
- Manifiesto con dataset, plan, modelo, cohorte, supuestos, hashes y fecha.
- Sin cartas, contactos, credenciales ni datos personales.

## 10. Migración desde el MVP

- Mantener IDs municipales (`ine:{entidad}:municipality:{clave}:2025-12-15`); añadir `level` y `district_plan`.
- Reingesta nacional; no reutilizar el `model_run_id` de Jalisco.
- Conservar el MVP como referencia y pruebas de regresión.
- Las rutas v1 ganan `level` con valor por defecto `municipality`; los clientes actuales siguen funcionando para Jalisco.
- La base distrital se migra con plan 2023; los agregados 2021 quedan en auditoría.
- No se borran datos del piloto hasta que la carga nacional y el ensayo limpio estén verificados.

## 11. Pruebas y aceptación

### Pruebas de datos

- 6 ZIP, 32 CSV, hashes; 54,872,712 filas; 2,477 municipios; 300 distritos.
- Conciliación `LN=SV+NV+NS` al 100%.
- Normalización de códigos; parser de Oaxaca; secciones sin `DEF` no imputadas.
- Cobertura de reconstrucción distrital ≥98% LN; distritos individuales ≥95%.
- Correspondencia 2,581 pares; 72 municipios partidos; ninguna asignación 1:1.

### Pruebas de modelo

- Cortes temporales; cohortes separadas; scaler sólo entrenamiento; 2024 congelado.
- Cambio de identidad/cohorte/candidato cambia `model_run_id`.
- Bandas y cobertura empírica; insuficiencia nunca cero.
- No suma de predicciones municipales para distrito.

### Pruebas de API/UI/GIS

- `level` filtra correctamente; no mezcla IDs.
- WMS/WFS por entidad; máximo de features; administración bloqueada.
- Selector de nivel y entidad; ficha municipal muestra distritos; ficha distrital muestra municipios; no jerarquía falsa.
- Fichas reconstruidas marcadas; insuficientes no verdes.
- Reportes por nivel; límites; fuente/plan/modelo.
- Accesibilidad y E2E nacional (una entidad, municipio, distrito).

### Criterios de aceptación nacional

1. 32 entidades cargadas y auditadas.
2. 2,477 municipios y 300 distritos publicados.
3. Dos modelos separados evaluados y versionados.
4. Selector municipal/distrital operativo.
5. Reconstrucción distrital trazable y con cobertura declarada.
6. Mapas nacionales eficientes y WFS por entidad.
7. Escenarios por nivel sin mezcla.
8. Reportes y exportaciones con fuentes/plan/modelo.
9. Pruebas críticas ejecutadas; incumplimientos documentados.
10. Sin datos personales ni promesas causales.

## 12. Fases

1. **Fundación nacional**: esquema por nivel, ETL de sección, agregados municipales/distritales, cartografía 32 entidades, PostGIS/GeoServer, API con `level`, selector y mapa básico.
2. **Municipio nacional**: cohorte/modelo/validación municipal, predicciones, fichas, escenarios y reportes municipales.
3. **Distrito nacional**: reconstrucción 2023, cobertura, cohorte/modelo distrital, fichas, mapa y escenarios; distritos insuficientes.
4. **Escala y cierre**: rendimiento, reportes, CI, ensayo limpio, documentación y revisión.

Cada fase tiene una verificación propia; no se avanza a distrito si la reconstrucción no supera el umbral.

## 13. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Distritos históricos no comparables | Plan explícito, reconstrucción por sección, cobertura y etiqueta; insuficiente si no alcanza |
| Municipios partidos | Puente sección→distrito y pares, nunca asignación dominante |
| 3.7 GB/55M filas | Fact particionada, COPY, agregados materializados, API sólo agregados |
| Calidad municipal desigual | Regla de calidad, exclusiones y reporte por entidad |
| Modelo distrital inestable | Validación temporal, M0/M1, banda, mínimos y no publicar si falta evidencia |
| WMS/WFS lento | WMS nacional, WFS por entidad/bbox, simplificación y caché |
| Licencias de datos | Gate de confirmación y atribución; no publicar crudo sin decisión |
| Cambios de plan futuro | `plan_id` versionado; no reutilizar claves |
| Alcance excesivo | Fases y aceptación por nivel; local districts fuera |

## 14. Decisiones pendientes de confirmación

- Nombre y visibilidad del repositorio nacional: se propone continuar en `ARELL31/participa-geo` (privado), rama de diseño.
- Plan distrital publicado: se propone **2023**; 2021 queda como auditoría.
- Umbral de reconstrucción: 98% nacional y 95% por distrito; el builder puede ajustar sólo con evidencia de la fase 1.
- Límites de escenarios: 1,000 municipios / 300 distritos; el builder puede reducirlos si el rendimiento lo exige.
- Fecha de entrega y prioridad de fases.

## 15. Lo que queda al builder

- Elegir versiones exactas de dependencias y migraciones.
- Diseñar las tablas físicas/índices/particiones y los jobs de carga.
- Resolver el parser y la reconstrucción con pruebas sobre los datos reales.
- Calcular cobertura y validar el umbral antes de publicar distritos.
- Definir la etiqueta de cabecera distrital desde el catálogo.
- Diseñar los contratos OpenAPI concretos y los tipos TS.
- Ajustar el diseño visual del selector y las fichas, respetando el design system.
- Ejecutar la fase 1 y reportar hallazgos antes de planificar la fase 2.

No se implementa nada hasta aprobar este diseño y escribir el plan técnico.

## 16. Resoluciones del builder check

Un revisor independiente formuló nueve preguntas de planificación. Estas resoluciones precisan el diseño y prevalecen sobre cualquier frase anterior que las contradiga.

### 16.1 Continuidad de secciones

No se unirá por número de sección a ciegas. La fase 1 construirá una **tabla de continuidad seccional validada** usando la capa `SECCION` del MGS, el catálogo histórico del INE y, si está disponible y licenciado, el archivo histórico `HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb`. Una sección sin vínculo validado se marca `unmatched`; no se le asigna un distrito por número. La tabla de continuidad es un artefacto versionado con evidencia y cobertura.

Si no se consigue una continuidad defendible para 2009/2012, esos años no alimentan el modelo distrital; el modelo municipal no se ve afectado. No se usará una unión cruda sección↔sección como sustituto.

### 16.2 Denominador de cobertura

Para cada distrito del plan 2023, el denominador de cobertura es la **LN de referencia 2024 de todas las secciones del distrito**; el numerador es la LN 2024 de las secciones que tienen un vínculo histórico validado para el año evaluado. Así se mide si la población actual del distrito está representada en la historia, sin que el crecimiento poblacional haga parecer incompleta una serie.

- Cobertura nacional del año = Σ LN2024 de secciones con vínculo / Σ LN2024 de todas las secciones del plan.
- Cobertura por distrito = Σ LN2024 de sus secciones con vínculo / Σ LN2024 de sus secciones.
- Las 450 secciones CCPC 2024 sin geometría y las 2,967 secciones MGS sin datos se cuentan como no cubiertas; no se inventan.
- Las 318/221 secciones sin `DEF` en 2009/2012 son `unmatched` para distrito, pero siguen contando en municipio si su clave municipal es válida.

### 16.3 Umbral y años

El umbral nacional es 98% de LN2024 cubierta por año requerido; el umbral por distrito es 95%. Se evalúa **por objetivo**, no por “modelo de un año”:

- objetivo 2015 requiere 2009/2012/2015;
- objetivo 2018 requiere 2012/2015/2018;
- objetivo 2021 requiere 2015/2018/2021;
- objetivo 2024 requiere 2018/2021/2024;
- objetivo 2027 requiere 2021/2024.

Si falla un año requerido para 2027, no se publican predicciones distritales 2027; se conserva historia/2024 observado y se informa. Si falla un año de entrenamiento/validación, el modelo distrital no se selecciona ni se publica. El umbral es una compuerta, no una métrica decorativa.

### 16.4 Distritos nuevos

“Distrito nuevo” significa **sin continuidad seccional histórica suficiente**, no “número que no existía”. Los 7 números que entran en el plan 2023 (BC09, Coahuila08, NL13/14, Puebla16, Querétaro06, Yucatán06) son elegibles si sus secciones tienen vínculo y cobertura; si no, quedan insuficientes. No se les asigna la serie de un distrito anterior por proximidad o número.

### 16.5 Ficha municipal–distrito

La ficha municipal mostrará **agregados por intersección municipio×distrito**, no filas de sección cruda. Se añade `agg_municipality_district_year` con LN/SV/NV/NS y shares agregados; la API expone sólo esos agregados. La ficha distrital muestra municipios/secciones como agregados; nunca datos personales.

### 16.6 `/participation/summary`

Devuelve, por entidad y año:

- conteos sumados desde secciones (LN/SV/NV/NS) y abstención conocida;
- `eligible_count`, `insufficient_count`, `high_risk_count` del nivel solicitado;
- `coverage_share` del nivel/plan.

El color del mapa nacional de entidades representa **abstención observada sumando conteos seccionales**, no un promedio de tasas municipales o distritales. La tabla y la ficha muestran los conteos por nivel. Así el mapa es comparable entre niveles y no viola la regla de no promediar tasas.

### 16.7 Compatibilidad v1

- `state_code` conserva el valor por defecto `"14"` para clientes existentes.
- Las consultas nacionales pasan explícitamente `state_code=all`; no se cambia el default.
- El modelo nacional reemplaza al modelo publicado; los artefactos de Jalisco quedan como referencia reproducible y pruebas de regresión de ingestión/GIS, no servidos en paralelo.
- Los IDs municipales existentes se conservan; se añade `level` y plan distrital.

### 16.8 Rendimiento medible

- WMS nacional GetMap 1200×900: 200 y ≤5 s en frío, ≤2.5 s en caliente.
- WFS por entidad/bbox: ≤1,000 features y ≤3 s.
- Listas API de hasta 500 elementos: ≤500 ms p95 en caliente.
- Resumen nacional de 32 entidades: ≤1 s.
- El mapa nacional usa WMS raster; WFS sólo por entidad/bbox. Las teselas vectoriales son una optimización posterior, no un requisito de la primera versión.

### 16.9 Fase de reconstrucción

La continuidad seccional, la reconstrucción 2023 y la compuerta de cobertura se construyen en la **fase 1**, junto con los agregados. La fase 2 (municipio) puede avanzar si la reconstrucción distrital no está lista; la fase 3 (distrito) no empieza hasta que la compuerta pase. Así el riesgo distrital no bloquea el valor municipal.

### 16.10 Conteo de municipios partidos

El número autoritativo para la tabla de correspondencia es **72**, derivado de la capa MGS 2023/2025. La cifra 70 corresponde a los municipios partidos observados en CCPC 2024 y 79 a 2021; se reportan como conteos de datos, no como la definición geométrica. Las pruebas comparan la tabla con la fuente y documentan la diferencia.

### 16.11 Límites de escenarios

Máximo 1,000 municipios o 300 distritos por escenario; cuerpos JSON hasta 128 KiB; los resultados se persisten completos para el nivel seleccionado. No se permite mezclar niveles ni planes en un mismo escenario. Un escenario nacional completo de municipios no se ofrece en la primera versión; se selecciona por entidad o subconjunto.

### 16.12 Decisiones cerradas

- Plan distrital publicado: **2023**; 2021 queda como auditoría.
- Reconstrucción: continuidad validada, umbral 98% nacional / 95% distrito.
- Dos modelos separados; sin suma municipio→distrito.
- WMS nacional + WFS por entidad/bbox; sin WFS nacional completo.
- Local districts fuera de alcance.
- El builder puede ajustar umbrales sólo con evidencia de fase 1 y aprobación del usuario.

