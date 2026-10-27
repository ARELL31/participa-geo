# PARTICIPA-GEO — Diseño del MVP de cuatro días

Fecha: 2026-10-26. Estado: **diseño aprobado; plan aprobado; ejecución por agentes autorizada**.

Registro de aprobación: el usuario respondió «Ok ya instale docker y si apruebo» a la solicitud de aprobación de este diseño con Jalisco, horizonte2027, referencia cartográfica2025, cobertura predictiva parcial por calidad y repositorio `/home/arell31/participa-geo`. La aprobación no elimina las limitaciones documentadas ni autoriza exposición pública.

## 1. Intención y acuerdos

Ayudar a personal técnico e institucional a analizar participación electoral municipal, estimar riesgo de abstención y comparar intervenciones hipotéticas, con neutralidad y sin inferencias individuales.

El usuario confirmó que el equipo está registrado y aprobó el enfoque A: piloto municipal de una entidad, frente a cobertura nacional por entidad. Plazo de trabajo declarado: cuatro días. La convocatoria establece entrega el 31 de octubre de 2026 a las 23:59; el cronograma interno debe finalizar antes de ese límite. No asumir zona horaria no publicada.

**Decisiones aprobadas tras la revisión del borrador:** Jalisco, proyección a elección federal intermedia2027, repositorio en `/home/arell31/participa-geo` y ejecución local medianteCompose. El usuario pidió aviso previo de instalaciones y confirmó que instaló Docker. El agente no ha instalado dependencias.

## 2. Objetivos, no objetivos y condiciones de fracaso

Objetivos obligatorios: historia municipal real; mapa publicado por GeoServer; modelo sencillo que incorpore historia y composición sociodemográfica agregada; evaluación temporal; semáforo comprensible; escenarios A/B con supuestos; recomendaciones preventivas y de priorización; exportaciones reproducibles; pruebas ejecutadas; documentación y entrega del Reto 2.

Fuera del MVP: autenticación, perfiles individuales, campañas partidistas, modelos de conducta individual, optimización de presupuestos, tiempos de viaje, accesibilidad avanzada, microservicios, colas, Kubernetes, reportes configurables y actualización automática periódica. Los módulos pendientes se identificarán como tales y no tendrán controles que aparenten funcionar.

Sería un fracaso: mapa bonito con cifras inventadas; tratamiento de no especificados como abstención; división aleatoria presentada como validación futura; datos posteriores al objetivo en predictores; efectos causales ficticios; comparación cartográfica no advertida; documentación administrativa omitida; declarar integración comprobada sin ejecutarla.

## 3. Alternativas consideradas

- **A, elegido por el usuario:** piloto municipal en una entidad. Mayor profundidad y posibilidad de revisar datos e integración, a costa de cobertura limitada.
- **B, descartado para esta entrega:** 32 entidades. Menor detalle y pocas unidades territoriales para evaluar asociaciones.
- Dentro de A se propone un monolito modular FastAPI y no servicios independientes: reduce coordinación y despliegue sin renunciar a módulos de dominio. Se conserva GeoServer como servicio geográfico independiente.

## 4. Evidencia de datos ya obtenida

Fuentes oficiales:

- Convocatoria: https://ine.mx/wp-content/uploads/2026/09/Convocatoria_Hackaton-1.pdf
- Micrositio: https://ine.mx/hackathon-2026/
- CCPC: https://ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/
- Manual: https://ine.mx/wp-content/uploads/2025/06/Manual-Conteos-Censales-2009-2024.pdf

Se inspeccionó el directorio ZIP, diccionario y cabecera de los 32 CSV de cada uno de los seis años. Se descargaron mediante HTTP Range sólo los miembros Jalisco, con lectura completa y comprobación CRC por `zipfile`, y se guardó SHA-256 del CSV descomprimido. No se verificó el checksum del ZIP nacional completo porque no se descargó completo.

URLs nacionales: `https://ine.mx/wp-content/uploads/2022/04/DatosAbiertos_DECEyEC_ConteosCensales{año}.zip` para 2009–2021; para 2024, `https://ine.mx/wp-content/uploads/2025/08/DatosAbiertos_DECEyEC_ConteosCensales2024.zip`.

Cabecera real común: `AELEC,FELECCION,EDOCVE,EDONOM,MPIOCVE,MPIONOM,SECCION,TIPOSEC,DEF,DEL,SEXO,EDAD,LN,SV,NV,NS`.

| Año | Filas Jalisco | Municipios | Secciones | LN | NS/LN |
|---|---:|---:|---:|---:|---:|
| 2009 | 472286 | 125 | 3351 | 5133870 | 2.1945% |
| 2012 | 473537 | 125 | 3452 | 5027267 | 0.1329% |
| 2015 | 497372 | 125 | 3570 | 5513033 | 3.4747% |
| 2018 | 503247 | 125 | 3570 | 5904226 | 6.5396% |
| 2021 | 513309 | 125 | 3613 | 6214764 | 3.3774% |
| 2024 | 539890 | 125 | 3787 | 6619379 | 5.8672% |

En esta inspección no aparecieron conteos negativos, claves duplicadas `(año, entidad, municipio, sección, sexo, edad)` ni incumplimientos de `LN = SV + NV + NS`. Estos son resultados de investigación, **no una suite del producto**.

Los 125 códigos y nombres municipales se conservan entre los seis CSV. En 2024 hay 2953 filas sin `DEL`; se retendrán con distrito local nulo porque el análisis es municipal y no se inventará un distrito. Sexo 2 aparece en 2024; ausencia histórica de esa categoría no significa conteo cero. Hay edades publicadas superiores a 100: se conservarán en bruto y se agruparán como 100+, sin alterar arbitrariamente los registros.

Los archivos 2009–2021 documentan distritos de marco 2021 y el de 2024 distritos de marco 2023, mientras que el tablero declara mayo2023. No afirmar que los ZIP son la extracción armonizada del tablero. El CCPC excluye casillas especiales y voto de residentes en el extranjero según los diccionarios; sus tasas no son intercambiables con cómputos electorales.

## 5. Geografía y correspondencias

Descarga oficial verificada:

- API: https://cartografia.ine.mx/sige8/api/bases/?producto=mgs&entidad=14&formato=Shapefile
- ZIP: https://cartografia.ine.mx/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/14.zip
- SHA-256 ZIP: `7b252438a67d904a42a7b912ff29bef74a2ed79675a609143e74a592ef872a50`.
- 125 registros municipales, 125 geometrías Polygon no nulas, nombres y códigos INE coincidentes con los seis CSV. CRS declarado: WGS84/UTM13N, EPSG:32613.

Pendientes: topología, transformación de CRS, importación PostGIS, correspondencias de límites a lo largo del tiempo y publicación GeoServer. Coincidencia de código y nombre prueba identidad de catálogo, **no igualdad geométrica histórica**. No se encontró el corte mayo2023 en los mecanismos consultados; no se afirma que no exista.

Decisión aprobada: cartografía INE2025 como **referencia posterior** para la consulta municipal y los dos escenarios2027. No hacer redistribución de conteos mediante intersección de secciones de distintos años. No presentar mapas de2009–2024 como si mostraran límites contemporáneos de cada elección. Toda unión analítica conservará año de observación y versión territorial por separado, y las fichas advertirán el límite de comparabilidad. Antes de asociar resultados a un municipio, comprobar catálogo de origen, catálogo de referencia y cambios administrativos documentados; cualquier división/fusión o identidad ambigua se marca no comparable y no recibe pronóstico hasta resolverla.

La igualdad histórica exacta de los límites NO se promete: si no se verifica, los mapas se describen sólo como representación sobre referencia 2025 y la serie como unidades administrativas reportadas por el INE, no como serie de superficie constante. Si esta limitación no es aceptada por el usuario, queda bloqueada la entrega GIS hasta conseguir cartografía/correspondencia histórica adecuada; no sustituir silenciosamente por otra fuente.

Regla operativa de correspondencia: distinguir `identity_status` (`verified_catalogue`, `ambiguous`, `known_changed`) y `footprint_status` (`verified_equal`, `not_verified`, `known_changed`). La coincidencia única de código INE, entidad y nombre normalizado en los seis CSV y catálogo INE2025 permite `verified_catalogue`; conservar la evidencia de comparación. Esta comprobación ya se ejecutó para125 municipios, pero no prueba ausencia de cambios de límites. La revisión documental añadirá incidencias administrativas encontradas: ausencia de resultados de búsqueda nunca se registra como igualdad geométrica probada. `identity_status=verified_catalogue` permite una serie de identidad administrativa y un pronóstico condicional sobre referencia2025, con `footprint_status=not_verified` visible. Identidad ambigua o división/fusión documentada se excluye hasta resolverla. Una serie de superficie constante exigiría `footprint_status=verified_equal` y está fuera del alcance no verificado. Son condiciones metodológicas que requieren aceptación expresa del usuario al aprobar este diseño.

INE e INEGI no son claves equivalentes: en la comparación nominal del agente GIS difieren en 90/125 municipios de Jalisco. La tabla de correspondencia derivada no se presenta como oficial. El MVP **no depende de INEGI**: obtiene composición por edad de LN de los propios CCPC. Censo2020/ECEG son ampliaciones, no parte del camino crítico ni fuente retroactiva para 2015/2018.

## 6. Indicadores y calidad

Por municipio/año, sumar conteos antes de calcular porcentajes:

- Participación conocida = `100 * SV / (SV + NV)`.
- Abstención conocida = `100 * NV / (SV + NV)`; objetivo del modelo.
- No especificados = `100 * NS / LN`.
- Límites de sensibilidad a registros NS = `[100*NV/LN, 100*(NV+NS)/LN]`, sólo tras reconciliar la identidad contable. Son cotas por datos desconocidos, no intervalos predictivos.

Datos con denominador cero: tasa nula y explicación, nunca cero por defecto. No promediar tasas municipales para agregados estatales. El modelo no estima probabilidad de abstención de una persona.

Política analítica conservadora, propuesta antes de entrenar: municipio/año elegible con `SV+NV >= 1000`, `NS/LN <= 0.10`, conteos válidos y correspondencia territorial sin ambigüedad. Conservar todos los municipios en tablas históricas; la exclusión afecta entrenamiento/evaluación/estimación, no borra los datos observados. Informar cobertura en municipios y en LN, tanto total como evaluable. La selección por calidad puede introducir sesgo de cobertura: documentarlo.

Con esta regla, y antes de revisar cambios administrativos, la inspección preliminar deja 116 filas elegibles para objetivo2015, 105 para2018, 91 para2021, 75 para2024 y 85 municipios con antecedentes elegibles para2027. Los restantes no se rellenan con predicciones ficticias; deben verse como información insuficiente. Los tamaños definitivos pueden bajar tras validación geográfica.

Cohorte común obligatoria: para cada retrospectiva, aplicar la regla de calidad al objetivo `t` y a **ambos** antecedentes `t-6` y `t-3`, además de la correspondencia de identidad. M0 y M1 se entrenan/evalúan y comparan sobre esas mismas filas; M0 no amplía cobertura al ser elegido. Para2027 se exige calidad de2021 y2024, no una calidad futura inexistente. Las exclusiones del objetivo retrospectivo sólo determinan qué errores son evaluables, nunca se introducen como predictores. Publicar además cobertura de datos observados frente a cobertura de cohorte común para no ocultar territorios excluidos.

## 7. Modelo y evaluación reproducible

**Horizonte propuesto:** abstención conocida municipal en elección federal intermedia2027, bajo continuidad de relaciones históricas. No usar judicial2025. Año y tipo objetivo se fijan en el MVP; no ofrecer pronósticos arbitrarios.

Para objetivo `t`, la fecha de origen del pronóstico es posterior a disponibilidad del CCPC `t-3` y anterior a elección `t`. Verificar fechas documentadas de publicación, especialmente para retrospectivas; guardar origen y `available_at` por fuente. Si no es posible demostrar disponibilidad real en una retrospectiva, llamarla evaluación retrospectiva por año de referencia, no reproducción perfecta de un pronóstico emitido entonces. No usar datos cuyo año de referencia sea futuro respecto al origen.

Referencia M0: tasa del mismo municipio y mismo tipo de elección en `t-6`.

Candidato M1: `StandardScaler` + `Ridge(alpha=1.0)` con intercepto y seis predictores:

1. Abstención conocida `t-6`, mismo tipo.
2. Abstención conocida `t-3`, última elección ordinaria.
3. Proporción LN de 18–29 años en `t-3`.
4. Proporción LN de 60+ en `t-3`.
5. Proporción LN en secciones rurales de `t-3`.
6. Indicador de elección intermedia (frente a presidencial).

Variables por edad se derivan de LN, no de la composición de quienes votaron en el año objetivo. Pesos iguales por municipio en ajuste; no interpretar LN como tamaño de una muestra binomial independiente. Sin búsqueda de hiperparámetros ni selección posterior de variables sobre el test. Estandarizar sólo con entrenamiento. Recortar salida al rango0–100, registrar frecuencia y evaluar resultados recortados igual que los servidos.

Esquema temporal:

| Uso | Objetivos de ajuste | Antecedentes | Año predicho |
|---|---|---|---|
| Validación y elección M0/M1 | 2015 y 2018 | Para cada objetivo, únicamente t-6 y t-3 | 2021 |
| Evaluación final | 2015, 2018 y 2021 | Misma regla | 2024 |
| Ajuste final de familia elegida | 2015, 2018, 2021 y 2024 | Misma regla | 2027 |

M1 se elige si reduce MAE municipal en2021 frente a M0; en empate permanece M0. Siempre publicar ambos modelos y métricas, incluidas las del candidato con sociodemografía si se despliega M0. La prueba2024 no puede usarse para cambiar familia, variables, umbrales ni alpha. Que el último test sea presidencial limita su transferencia a2027; se destacan por separado los resultados intermedios2021.

Métricas: MAE y RMSE en puntos porcentuales, sesgo, y MAE ponderado por denominador conocido del objetivo como indicador secundario. Reportar número de municipios, cobertura y lista de exclusiones por cada corte. No confundir muchos municipios con muchos ciclos temporales; sólo hay tres elecciones de cada tipo. No exigir una mejora inventada para aprobar la entrega: si la referencia gana, se comunica.

Explicación: referencia = antecedente del mismo tipo; candidato = coeficientes y contribuciones aditivas por municipio en la escala transformada. Mostrar intercepto, media/escala y advertencia de asociación no causal; si hubo recorte, explicar que la suma corresponde al valor previo al recorte.

## 8. Incertidumbre y semáforo

No mostrar un supuesto intervalo binomial sobre LN como si resolviera incertidumbre futura. Guardar errores fuera de tiempo de la familia elegida. Para2027, banda simétrica con amplitud igual al percentil90 absoluto de errores2021 (elección intermedia), recortada a0–100. La banda se denomina **rango de error histórico de referencia**; no se promete cobertura90% futura. Publicar también cobertura empírica del rango al compararlo con errores2024, sin ajustarlo con ese resultado. Pocos ciclos, dependencia espacial y cambio de distribución limitan su interpretación. Si no hay al menos30 municipios de error elegible, no publicar banda ni clasificar con apariencia de certeza.

Semáforo analítico, no clasificación oficial INE:

- Bajo: abstención estimada <40%.
- Medio: 40% a <50%.
- Alto: >=50%.
- Información insuficiente: no elegible o correspondencia territorial pendiente.

50% identifica mayoría del universo con participación conocida que no votaría;40% introduce una franja preventiva de10 puntos. Son criterios normativos explícitos, no umbrales aprendidos para mejorar métricas. Mostrar porcentaje, banda y estabilidad de categoría si la banda cruza un umbral; no degradar automáticamente a una categoría de menor riesgo por incertidumbre. En ambos escenarios los umbrales son idénticos.

## 9. Escenarios y recomendaciones

A = predicción2027 sin ajuste, bajo supuestos de continuidad del modelo. No es un contrafactual causal identificado.

B = cambio aritmético hipotético: `abstención_B = max(0, abstención_A - reducción_pp)` sólo en municipios seleccionados y elegibles. Control explícito de reducción entre0 y10 puntos porcentuales; no confundir puntos con porcentaje relativo. El usuario elige una justificación de catálogo `assumption_code`, enum `preventive_exploration` o `model_sensitivity`; su texto explicativo procede de una plantilla revisada. **No hay campos de texto libre** en el MVP, para impedir que una justificación contenga nombres u otros datos personales. Hasta125 municipios por escenario, sin geometrías ni fórmulas libres como entrada. Rechazar NaN, infinito, duplicados, identificadores desconocidos y campos adicionales (`extra=forbid`).

Los0–10 puntos son un límite de exploración del MVP, no rango de eficacia respaldado. B hereda el mismo rango de error por desplazamiento limitado a0–100, etiquetado como banda de A trasladada condicionalmente al supuesto; no agrega evidencia ni cuantifica incertidumbre del efecto. No modificar historia ni artefacto del modelo.

Mapas A/B usan exactamente la misma referencia2025, selección y leyenda; tabla de diferencias y supuestos exportables. Guardar selección, reducción solicitada y efectiva, código y texto de justificación controlados, origen anónimo/no autenticado (sin identificador personal), fecha, hash de datos y versión de modelo. No estimar personas adicionales movilizadas en2027 sin proyección validada de LN.

Recomendaciones basadas en reglas legibles, no persuasión segmentada: revisar datos de territorios con NS elevado; considerar información cívica y revisión institucional en alto riesgo; monitorear categoría inestable; evaluar equidad mediante cobertura territorial y tamaño LN observado, sin convertir el resultado en obligación. Incluir prioridad de mejora de datos y reconocer sesgo de exclusión. El módulo avanzado de recursos no está implementado.

## 10. Arquitectura y repositorio propuestos

Cuatro servicios iniciales Compose: web, api, db(PostgreSQL/PostGIS) y geoserver. ETL, entrenamiento y entrega son comandos de la misma imagen Python, no servicios permanentes adicionales. Backend publica REST y lee artefactos precomputados; GeoServer sólo publica vistas/tablas con permisos de lectura.

Estructura propuesta después de aprobación:

```text
apps/web/
apps/api/participa_geo/{api,db,indicators,prediction,scenarios,reporting}/
pipelines/{ingestion,validation,training}/
gis/{geoserver,styles}/
data/{raw,processed,samples}/
infrastructure/{docker,scripts}/
tests/{integration,e2e}/
docs/{architecture,methodology,design-system,decisions,hackathon,superpowers}/
.github/workflows/
README.md
compose.yaml
.env.example
```

Un `pyproject.toml` y lock Python para backend/tareas; un `package.json` y lock en web. Datos oficiales brutos y secretos fuera de Git; fixtures pequeños inequívocamente sintéticos sólo para tests, nunca en pantallas reales. Registro de fuentes y checksums en Git. Contenedores Linux con versiones/digests verificados al implementar, no etiquetas `latest`. Propuesta técnica: Python3.12 y Node24 LTS en imágenes; versiones exactas del resto se fijan verificando fuentes y compatibilidad antes de instalar.

Modelo conceptual mínimo:

- `dataset_version`: fuente, año, fecha de publicación nullable, recuperación, checksum, licencia/condiciones y diccionario.
- `territory_version`: UUID, sistema INE, entidad, código municipal, nombre, corte, geometría4326 **nullable** y procedencia. Las identidades de origen por año pueden carecer de geometría; sólo la referencia2025 recibe el polígono descargado. No copiar geometría2025 a una fila etiquetada como2009/2012/etc.
- `territory_correspondence`: territorio origen/referencia, tipo de relación, evidencia, `identity_status` y `footprint_status`; nunca equivalencia inferida por concatenación INEGI.
- `observation`: municipio origen, año/tipo, LN/SV/NV/NS, proporciones agregadas y banderas. Unicidad territorio/año/dataset.
- `model_run`: familia, parámetros, features, fechas/cortes, hashes, dependencias, métricas y exclusiones.
- `prediction`: ejecución, municipio de referencia, objetivo2027, estimación/banda/riesgo o estado insuficiente.
- `scenario`, `scenario_result`: supuestos y resultados derivados trazables.
- `report_artifact`: formato, hash de selección/supuestos, fuentes, modelo y fecha; almacenamiento acotado.

Alembic crea esquemas y restricciones; roles separados para migración/escritura, API y lectura GIS. No guardar CSV por sección/sexo/edad como tabla pública; servir únicamente agregados municipales. Geometría se transforma realmente de32613 a4326, no se cambia sólo la etiqueta. Registrar y validar reparaciones; no aceptar geometrías vacías. MapLibre usa WMS raster EPSG:3857 para visualización y WFS GeoJSON4326 con filtros por municipio/bbox para interacción. Limitar features, extensiones y tamaño; no descargar el seccional nacional en navegador. Con125 municipios no se justifica vector tiles.

Base cartográfica opcional: preferir vista de polígonos con fondo neutro para que la demo no dependa de tiles externos. Si se usa fondo público, documentar licencia y atribución. Exportación mapa debe provenir de las mismas vistas/estilos y contener corte, leyenda, escenario y versión.

## 11. Contratos API del MVP

Prefijo `/api/v1`, OpenAPI como contrato y generación de tipos TypeScript para evitar duplicación. Tasas de la API en puntos0–100, composición en fracciones0–1 con nombres `_share`; enteros para conteos. Fechas ISO8601UTC. UUID como identificador público, nunca aceptar SQL o filtros CQL arbitrarios.

| Método/ruta | Contrato |
|---|---|
| GET `/health/live` | Proceso responde; no equivale a datos listos. |
| GET `/health/ready` | DB, migraciones, dataset/modelo requerido y capa GIS disponibles;503 si falta requisito. |
| GET `/territories` | Filtros `state_code=14`, `level=municipality`, búsqueda acotada, `page>=1`, `page_size=1..125`; lista con IDs, nombre, código INE, corte y comparabilidad. |
| GET `/participation/history` | `territory_id` opcional, `year` opcional enum2009/2012/2015/2018/2021/2024, misma paginación; estado agregado si no hay municipio y tasas calculadas por sumas. Retorna conteos, tasas conocidas, cotas NS y calidad. |
| GET `/models` y `/models/{id}` | Ejecuciones ya entrenadas, métricas por corte, features, referencias, limitaciones. Sin endpoint de entrenamiento. |
| GET `/predictions` | `model_run_id` del despliegue, `target_year=2027`, municipio opcional, paginación; incluye insuficientes y causa, nunca valor0 sustitutivo. |
| POST `/scenarios` | Cuerpo `{model_run_id, target_year:2027, territory_ids, reduction_pp, assumption_code}`;201 con UUID, A/B, diferencias y supuestos. Entradas acotadas según sección9. Sin campos libres. |
| GET `/scenarios/{id}` | Recupera comparación persistida o404. |
| GET `/recommendations` | Filtros equivalentes a predicciones, reglas/versiones y justificación; sin optimización presupuestaria. |
| POST `/reports` | Solicitud de exportación de plantilla fija: tipo (`history_csv`, `history_xlsx`, `scenario_csv`, `scenario_geojson`, `scenario_pdf`, `scenario_map_png`, `scenario_map_pdf`, `methodology_pdf`, `executive_pdf`, `technical_zip`), `scenario_id` cuando corresponda y selección acotada. Exportaciones pequeñas se completan en la petición con200(cache)/201(nueva); documentos institucionales sólo sirven artefactosCLI ya generados, o409 `institutional_package_not_generated`. Nunca entrena ni crea trabajos pendientes sin ejecutor. `scenario_csv` concreta en el plan la exportación tabular de escenarios ya requerida, sin cambiar el alcance aprobado. |
| GET `/reports/{id}` y `/reports/{id}/download` | Metadatos/estado (`ready`, `failed`) y descarga o409 si falló. Sin rutas de archivo aportadas por usuario. |

La entrega metodológica/ejecutiva/ZIP técnico se genera mediante CLI reproducible y se registra como artefacto; la API sirve los resultados. CSV/XLSX/GeoJSON municipal, fichaPDF y mapas comparativosPNG/PDF deben generarse **sin intervención del operador desde la UI**. Acotar a750 filas históricas o125 resultados municipales por escenario, una solicitud activa por cliente y tiempo totalmáximo30s; exceder límites retorna error explícito y nunca un archivo parcial presentado como éxito. Cachear porhash y escribir artefactos atómicamente. No hay cola ni estadospendientes.

Los mapas comparativos usan dos GetMap internos de GeoServer (A/B), resoluciónmáxima1200x900px cadauno y timeout5s por llamada. ComponerPNG/PDF con leyenda, corte, fuentes y versión. Las capas/vistas publicadas sólo leen geometrías y resultados ya calculados; filtros de escenario se construyen en servidor desde UUID validado, no se aceptan CQL niSQL arbitrarios. Si GeoServer falla, la exportación de mapa falla explícitamente, no se sustituye por imagen decorativa. Definir en el plan comandos concretos, límitesdetamaño y pruebas de cadaformato.

Listas retornan `{items, page, page_size, total, meta}`; `meta` incluye versiones, fuentes/corte y filtros aplicados. Errores `application/problem+json`, campos estables `type,title,status,detail,instance,code,request_id`, sin trazas privadas;400/422 entrada,404 recurso,409 estado,413 tamaño,503 prerequisitos. Ordenamiento estable por código INE.

Fijar ejemplos JSON y pruebas de contrato en el plan antes del primer endpoint. No publicar endpoints de priorización/accesibilidad ficticios.

## 12. UX y diseño corporativo

Se conserva el Application Shell solicitado: sidebar, header, filtros globales de territorio y periodo, metodología accesible. Rutas funcionales para resumen, territorio, modelo, escenarios y entrega. Recursos avanzados y accesibilidad indicados como pendientes. Filtros serializados en URL y usados como claves de TanStack Query; no copiar resultados entre años o modelos. Año histórico y objetivo2027 son controles semánticamente diferentes: nunca aplicar el año histórico al pronóstico como si fuera entrenable al vuelo.

React/TypeScript/Vite, MapLibre, TanStack Query, Radix/shadcn según componentes necesarios, variablesCSS y Lucide. Una sola familia de componentes; sin librerías redundantes. Inter local con licencia conservada, escala base16px, separación basada en4/8px, esquinas discretas. Paleta exacta del usuario: primary#6F1739, hover#54102A, secondary#8B1E3F, accent#AD536D, background#F7F6F5, surface#FFFFFF, text#252525, secondary-text#666666, border#E6E0E2.

El borde suave no es suficiente como único indicador de control/foco: añadir indicadores con contraste medido. Estados semánticos de riesgo pueden usar colores propios, siempre junto con texto/icono y tabla equivalente. No asumir AA por usar Radix. Verificar contraste, foco no oculto, formularios etiquetados, navegación por teclado, zoom200%, reflujo a320pxCSS, vista375px y escritorio, lector de pantalla en controles críticos y alternativa tabular al mapa. Respetar movimiento reducido; no usar animación decorativa. No añadir dark mode al MVP.

Identificar observación/predicción/hipótesis, denominador conocido, NS, cobertura y cartografía. No mostrar datos sintéticos en producción ni números durante errores/carga como si fueran reales. Estados de carga, error, vacío y datos insuficientes son contratos de cada consulta. Ningún tooltip contiene información esencial sin alternativa por foco/texto.

UI UX Pro Max está disponible y se ejecutó: las búsquedas de sistema global devolvieron parcialmente un patrón comercial fuera de contexto, incluso tras reintento; no se persiste como diseño aprobado. Sí se adoptó la guía específica de gráfico de pronóstico (histórico continuo, predicción discontinua, banda nombrada y tabla), adaptando escalas electorales y colores corporativos; no usar recomendaciones de ventanas diarias de ese resultado. La maqueta visual se revisará con el usuario si desea verla; este documento no sustituye esa revisión ni afirma que exista UI.

## 13. Entregables y generación

- Reporte metodológico/preventivoPDF:10–15 páginas, variables, universo CCPC, calidad, correspondencias, método, validación, incertidumbre, semáforo, escenarios, recomendaciones/priorización, fuentes y limitaciones. Plantilla con texto revisado y resultados reales; no rellenar páginas para aparentar metodología.
- Presentación ejecutivaPDF: máximo10 diapositivas, problema/fuentes/método/evidencia/riesgos/escenarios/propuesta/limitaciones.
- CSV y XLSX agregados municipales con datos usados, features, exclusiones y diccionario. GeoJSON con A/B, resultados y referencia territorial; no polígonos inventados.
- Mapas comparativos enPDF/PNG, leyenda compartida, fuente y fecha.
- Código, instrucciones, evidencia y manifiesto/checksums en `technical_zip` identificado por equipo/eje, descargable desde laUI una vez generado porCLI. No contiene cartas, contactos ni otros datos personales.
- Cartas oficiales de cesión y declaratoria: el usuario aporta firmas y revisa condiciones. **Fuera del repositorio público y de cualquier imagen/contenedor**. El ZIPinstitucional final lo integra y revisa el usuario en un espacio privado, añadiendo las cartas alZIPtécnico. No se sirve por laAPI, ni se sube aGit, ni se automatiza su envío. Datos administrativos nunca entran almodelo.

Reproducibilidad: `technical_zip` incluye los seisCSVoficiales íntegros deJalisco, el ZIPcartográficooriginal de10MB, diccionarios, agregados municipales, correspondencias verificadas, artefacto de modelo y métricas, fuentes ychecksums. No depende de `/tmp/opencode` ni de la persistencia de esta sesión. Antes de redistribuir originales revisar condicionesdeuso; si éstas no permiten inclusión, informar el bloqueo y pedir alternativa, no quitar datos silenciosamente. Los brutos permanecen fuera deGit; el paquete técnico los incorpora como archivos públicos agregados en su granularidad original, nunca listasnominales con identificadorespersonales. La API de consulta y las exportacionesanalíticas sólo exponen agregados municipales; el ZIPdereproducción es la excepción documental explícita que incluye los archivos públicosfuente y no ofrece consultas por celda sección/sexo/edad. Advertir riesgo de celdas pequeñas y prohibición de inferenciaindividual; ningún campo de identificadorpersonal es admitido por los esquemas.

La ejecución analítica desde elZIP no debe volver a descargar datosoficiales: validarchecksums y trabajar con las fuentes empaquetadas. Una instalaciónlimpia puede necesitar internet para imágenes y dependencias conlocks; no se promete instalacióntotal sinred ni se incluyen imágenesDocker en elZIP. El entrenamiento se reproduce con las versionesbloqueadas; registrar toleranciasnuméricas para métricas y predicciones. Fecha/hora del reporte es metadato variable, no exigir ZIPbinariamente idéntico.

Propuesta de generación: `ReportLab` paraPDF e informe/presentación, `openpyxl` paraXLSX y `matplotlib` para gráficos estáticos compartiendo resultados/tablas; GeoPandas para geometrías, ZIP/CSV de biblioteca estándar y composiciónPNG mediantePillow, dependencia habitual de la generaciónPDF que se declara explícitamente. Verificar dependencias/licencias y avisar antes de instalar. No atribuir al equipo propiedad intelectual de bibliotecas/cartografía/datos de terceros: conservar licencias/atribuciones y pedir al usuario revisar el alcance de cesión sobre aportacionesoriginales. Un manifiesto identifica modelo, fuente, corte, exclusiones, fecha, filtros y supuestos en todos los artefactos. Comprobar número de páginas con `pypdf` en pruebas. No automatizar firmas ni envío por correo; la revisión y entrega final son humanas.

## 14. Seguridad y entorno

MVP local: sólo puerto web/APIproxy en loopback; DB sin puerto host; GeoServer administrativo sólo en red interna o acceso local restringido mediante perfil de administración. Rutas públicas GIS limitadas a WMS/WFS de sólo lectura; deshabilitar WFS-T, REST administrativa y capas brutas. API y GeoServer usan rolesDB separados con mínimos permisos; CORS de origen exacto o mismo origen porproxy.

Sin credenciales por defecto publicadas; `.env.example` sin secretos y variables obligatorias para iniciar. No usar valores de usuario enSQL/HTML sin parametrizar/escapar. Escapar fórmulas potenciales enCSV/XLSX. LogsJSON con request_id y eventos de versión, sin credenciales ni datos administrativos; límites de payload y de selección, timeouts y protección frente a exportaciones repetidas (cachehash, máximo10 escenarios/artefactos nuevos por minuto por cliente para demo y cuotas de disco). No aceptar URLs ni plantillas de reporte del usuario.

Para despliegue público se requiere aprobación adicional, HTTPS, revisión de exposición y límites; este diseño no autoriza exponer la VM ni abrir firewall.

Entorno observado: AlmaLinux10.2 enWSL2, systemd, x86_64, ~8GBRAM. Python3.12.15 y Git2.52.0 disponibles; no se encontró Docker, Node/npm ni bibliotecas científicas enPython global. Propuesta: sólo DockerEngine+Compose en host; dependencias de aplicación dentro de contenedores, Playwright/Chromium en imagen de test, un worker. Objetivo de recursos: GeoServer heap<=1GB, PostgreSQL<=1GB para demo, no ejecutar entrenamiento y varias pruebas de navegador simultáneamente. Capacidad efectiva se mide, no se promete por configuración.

Actualización del entorno tras aprobación: el usuario instaló DockerEngine29.9.2 y Compose5.6.1; `docker.service` está activo. El proceso inicial de la sesión no tenía el grupo998/docker, aunque la cuenta ya estaba incluida. `sg docker -c 'docker version'` confirmó acceso a cliente y servidor29.9.2 sin cambiar permisos ni membresías. Los comandosDocker pueden ejecutarse bajo ese grupo mientras persista la sesión antigua. No se ha usado sudo ni instalado paquetes desde el agente.

## 15. Pruebas, revisión y criterios de aceptación

TDD en código de producto. Unitarias: agregaciones/denominadores/NS, fechas, esquemas, transformaciones, límites, semáforo, reglas escenarios, exportaciones. Estadísticas: splits por año, fuente/fecha de cada feature, ajuste de scaler sólo en train, reproducción por hash/semilla, ausencia de fuga, métricas y referencia, banda sin garantías falsas, exclusiones estables. No entrenar hasta cerrar la especificación.

Integración real con PostGIS y Alembic: restricciones, consultas y transformaciones espaciales. GIS: GetCapabilitiesWMS/WFS, GetMap con imagen válida, GetFeature con125 municipios/cobertura efectiva y valoresconsistentes, bloqueo de escritura/admin. Frontend: Vitest/TestingLibrary; Playwright con filtro→historia→predicción o insuficiente→escenario→exportación, acceso por teclado, errores y datos ausentes; axe como apoyo, no certificaciónAA.

Entrega aceptable sólo si: datos verificables; instalación limpia medianteCompose desde elZIPtécnico sin dependencia del espacio localdeinvestigación; capaGISfuncional; historia consultable; modeloevaluado; semáforoexplicado; A/Bcon supuestos; recomendaciones; exportaciones válidas; pruebas críticas ejecutadas; reporte/presentación dentrode límites; documentación y cartascompletas; identidad coherente; sinpersonales en análisis/API/ZIPtécnico ni promesascausales. El paquetefinal sí incluye lascartasadministrativas exigidas en un circuito privado separado. Aceptación técnica automática y confirmaciónadministrativa humana se registran por separado: no declarar listo para concurso hasta que el usuario confirme cartas y composición final. No ocultar incumplimientos: registrar bloqueo, impacto y alternativa aprobada.

El último día debe reservar margen a instalación desde cero, revisión independiente, corrección de causas raíz y comprobación de todo elZIP. Una prueba no ejecutada se registra como no ejecutada. CI debe ejecutar lint/tipos/unitarias/contratos; integraciónGIS pesada local con evidencia y smoke automatizado cuando el runner lo permita.

## 16. Distribución de trabajo y decisiones pendientes

Día1: aprobación, entorno, contratos, ETL+agregados+GIS y documento metodológico vivo. Día2: modelo/evaluación/artefactos+API. Día3: UI y escenarios/exportación. Día4: pruebasintegradas, revisión, reproducción y paquete. No es aún el plan técnico de implementación; `writing-plans` se invocará sólo después de aprobación del diseño.

Paralelismo únicamente con contratos cerrados, archivos sin conflicto y revisión central. InvestigaciónGIS independiente ya realizada; no se crearon agentes configurados ni se asumieron roles preexistentes. Revisar especificación con un agente fresco antes de presentarla.

Quedaron aprobados por el usuario: Jalisco; objetivo2027; uso transparente de referencia cartográfica2025 con limitaciones; cobertura predictiva parcial por calidad; ubicación del repositorio. Lasfeatures, reglasdecalidad, bandaempírica, umbrales, límitesescenarios y simplificaciónmodular son decisiones técnicas incluidas en el diseño aprobado. Sigue pendiente la aprobación del plan técnico y método de ejecución antes de implementar.

Le queda al implementador resolver versiones/digests concretos comprobados, librerías mínimas de componentes, nombresinternos, serialización deartefactos, estilosSLD y ejecución de comandos/pruebas, sin cambiar alcance o metodología aprobados. Un bloqueo real de cartografía/modelo/entorno se informa antes de sustituir tecnología o datos.

## 17. Revisión independiente del diseño

Un revisor fresco formuló seis preguntas de integración; se resolvieron como decisiones técnicas incluidas en el diseño: cohorte comúnM0/M1; identidad administrativa separada dehuella histórica y geometríaorigennullable; ZIPtécnico público separado delZIPfinalprivado; exportacionespequeñas síncronas y mapascon tipos explícitos sincola; fuentesempaquetadas para reproducir sin archivos deesta sesión; justificaciones decatálogo en lugar detextolibre. El usuario aprobó posteriormente el diseño completo. Aún no hay implementación de producto ni pruebas de aplicación ejecutadas.
