# Diccionario de datos — Conteos Censales de Participación Ciudadana (CCPC)

Fuente oficial: INE, «Conteos censales de participación ciudadana 2009–2024»
(https://ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/).
Para el MVP se ingieren los miembros **Jalisco** (entidad `14`) de los seis ZIP
nacionales. Manifiesto y checksums: `data/sources.json`; evidencia de la
inspección: `docs/methodology/evidence/jalisco-audit.json` y
`docs/methodology/evidence/ccpc-inventory.json`.

## Universo

| Propiedad | Valor |
|---|---|
| Entidad | Jalisco, clave INE `14` |
| Años | 2009, 2012, 2015, 2018, 2021, 2024 |
| Municipios por año | 125 |
| Filas fuente totales | 2 999 641 |
| Observaciones municipales agregadas | 750 (= 125 × 6) |

El CCPC excluye casillas especiales y el voto de residentes en el extranjero;
sus tasas **no** son intercambiables con cómputos electorales.

## Esquema fuente (allowlist exacta de 16 columnas)

El orden de columnas es fijo; cualquier desviación se rechaza (fail closed):

| # | Columna | Tipo | Descripción |
|---|---|---|---|
| 1 | `AELEC` | int | Año de la elección (2009–2024). Debe coincidir con el año esperado. |
| 2 | `FELECCION` | str | Fecha de la jornada electoral (formato corto, `d/m/aaaa`). |
| 3 | `EDOCVE` | str | Clave INE de entidad federativa (`14`). |
| 4 | `EDONOM` | str | Nombre de la entidad (`JALISCO`). |
| 5 | `MPIOCVE` | str | Clave INE de municipio; se normaliza a 3 dígitos conservando el valor. |
| 6 | `MPIONOM` | str | Nombre del municipio. |
| 7 | `SECCION` | str | Sección electoral. |
| 8 | `TIPOSEC` | str | Tipo de sección: `U` (urbana), `M` (mixta), `R` (rural). |
| 9 | `DEF` | int \| null | Distrito Electoral Federal (marco de la DERFE correspondiente). |
| 10 | `DEL` | int \| null | Distrito Electoral Local (marco de la DERFE correspondiente). |
| 11 | `SEXO` | int | `0` hombres, `1` mujeres; `2` aparece sólo en 2024. |
| 12 | `EDAD` | int | Edad cumplida a la jornada; debe ser `>= 18`. |
| 13 | `LN` | int | Lista nominal de los cuadernillos (>= 0). |
| 14 | `SV` | int | Registros con marca de voto (>= 0). |
| 15 | `NV` | int | Registros sin marca de voto (>= 0). |
| 16 | `NS` | int | Registros no especificados en participación (>= 0). |

## Invariantes y validación

- **Identidad contable**: `LN = SV + NV + NS` en toda fila; su violación se
  rechaza.
- **Conteos enteros no negativos** en `LN/SV/NV/NS`.
- **`NS` no es abstención**: son cuadernillos sin marcas, no disponibles,
  solicitados por autoridad jurisdiccional o páginas no disponibles. Se conserva
  como categoría propia y nunca se reclasifica a `NV`.
- **Clave de fila única**: `(AELEC, EDOCVE, MPIOCVE, SECCION, SEXO, EDAD)`. Los
  duplicados se rechazan.
- **Categorías ausentes no se infieren**: `SEXO=2` sólo se admite en 2024; su
  ausencia histórica no equivale a un conteo cero.

## Valores faltantes (conservados como nulos, nunca imputados)

| Año | Filas con `DEF` nulo | Filas con `DEL` nulo |
|---|---:|---:|
| 2009 | 1 723 | 1 723 |
| 2012 | 926 | 926 |
| 2015 | 0 | 0 |
| 2018 | 0 | 0 |
| 2021 | 0 | 0 |
| 2024 | 0 | 2 953 |

El análisis es municipal, por lo que el distrito nulo se retiene tal cual; no se
inventa un distrito. (La nota de investigación sólo registró el faltante `DEL` de
2024; esta tarea confirma además `DEF`/`DEL` en blanco en 2009 y 2012.)

## Edades

- `EDAD >= 18` (se rechazan filas con edad inferior).
- Las edades publicadas superiores a 100 (máximo observado 137) se conservan
  **en bruto** en la fuente; para reportes se agrupan como «100+» sin recodificar
  los datos.

## Columnas derivadas (artefacto `municipal-observations.parquet`)

Agregación municipal por año (suma de conteos antes de calcular cualquier tasa):

| Columna | Tipo | Definición |
|---|---|---|
| `year`, `state_code`, `municipality_code`, `municipality_name` | — | Clave y nombre municipal. |
| `ln`, `sv`, `nv`, `ns` | int | Conteos sumados. |
| `young_share` | float (0–1) | Proporción de `LN` con edad 18–29. |
| `senior_share` | float (0–1) | Proporción de `LN` con edad 60+. |
| `rural_share` | float (0–1) | Proporción de `LN` en secciones rurales (`R`). |
| `participation_pct` | float (0–100) | `100 * SV / (SV + NV)`; nulo si denominador cero. |
| `abstention_pct` | float (0–100) | `100 * NV / (SV + NV)`; nulo si denominador cero. |
| `unknown_share` | float (0–1) | `NS / LN` (fracción, no porcentaje). |
| `ns_lower_pct`, `ns_upper_pct` | float (0–100) | Cotas de sensibilidad `[100·NV/LN, 100·(NV+NS)/LN]`. |
| `eligible` | bool | Resultado de la regla de calidad (véase `quality.md`). |
| `source_version_id` | str (UUID) | `uuid5` del dataset por `(año, SHA-256)` del CSV. |
| `observation_id` | str (UUID) | `uuid5` de origen `ccpc:14:municipality:{código}:{año}`. |
| `territory_id` | str (UUID) | `uuid5` de referencia `ine:14:municipality:{código}:2025-12-15`. |

Los denominadores demográficos (`young/senior/rural_share`) usan `LN`, **no** el
electorado `SV`. Las unidades están fijadas: `unknown_share` es fracción 0–1; las
tasas de la API se publican en puntos porcentuales 0–100.

## Identificadores reproducibles

- Referencia territorial: `uuid5(NAMESPACE_URL, 'ine:14:municipality:{código3}:2025-12-15')`.
- Observación de origen: `uuid5(NAMESPACE_URL, 'ccpc:14:municipality:{código3}:{año}')`.
- Versión de dataset: `uuid5(NAMESPACE_URL, 'ccpc:14:dataset:{año}:{sha256}')`.

No se usan UUID aleatorios: los identificadores se derivan del contenido para que
los joins sean reproducibles.
