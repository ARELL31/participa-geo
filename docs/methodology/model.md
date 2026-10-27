# Modelo interpretable — abstención municipal 2027

Fecha: 2026-10-26. Alcance: T4. El modelo se entrena y evalúa **fuera de las
consultas HTTP**; la API sólo lee los artefactos precomputados.

## Horizonte y objetivo

- **Objetivo**: abstención conocida municipal en la elección federal intermedia
  de **2027**, bajo continuidad de las relaciones históricas. No se usa la
  judicial de 2025.
- **Abstención conocida** = `100 · NV / (SV + NV)`; el `NS` nunca se reclasifica
  como abstención.
- **Universo**: 125 municipios de Jalisco (referencia cartográfica INE 2025-12-15).
- **Disponibilidad**: como no se documentó la fecha de publicación de los CCPC,
  las retrospectivas se presentan como *evaluación retrospectiva por año de
  referencia*, no como reproducción de un pronóstico operativo emitido entonces
  (Spec §7).

## Cohorte común

Para un objetivo retrospectivo `t`, un municipio entra a la cohorte sólo si la
regla de calidad se cumple en `t`, `t-3` y `t-6`, **y** su identidad de catálogo
es `verified_catalogue` (la huella `known_changed` también lo excluye). Para 2027
se exige calidad en 2021 y 2024 (no existe calidad futura). M0 y M1 se entrenan,
evalúan y comparan sobre exactamente las mismas filas; elegir M0 no amplía la
cobertura.

La regla de calidad (`docs/methodology/quality.md`): conteos válidos
(`LN = SV + NV + NS`), `SV + NV >= 1000` y `NS/LN <= 0.10`. Los estados de
identidad se leen de PostGIS (T3) y nunca se asumen: si no se puede leer el
catálogo, el entrenamiento falla de forma estrepitosa.

## Familias

- **M0 (referencia)**: abstención conocida del mismo municipio y mismo tipo de
  elección en `t-6`. Para 2027, la tasa de 2021.
- **M1 (candidato)**: `StandardScaler` + `Ridge(alpha=1.0)` con intercepto y seis
  predictores, en este orden exacto:

| # | Feature | Origen |
|---|---|---|
| 1 | `same_type_abstention_pct` | `t-6` |
| 2 | `previous_abstention_pct` | `t-3` |
| 3 | `previous_young_share` | `t-3` (18–29 / LN) |
| 4 | `previous_senior_share` | `t-3` (60+ / LN) |
| 5 | `previous_rural_share` | `t-3` (secciones rurales / LN) |
| 6 | `is_midterm` | estructural (1 intermedia, 0 presidencial) |

El escalador se ajusta **sólo** sobre las filas de entrenamiento; no hay búsqueda
de hiperparámetros ni selección de variables sobre el test. La salida se recorta
a `[0, 100]` y se registra la frecuencia de recorte.

## Resultado (datos reales, computados)

La referencia **M0 gana**: MAE 2021 de 4.93 pp frente a 8.90 pp de M1. M1 aprende
de 2015 (intermedia) y 2018 (presidencial) que las intermedias tienden a menor
abstención (`coef(is_midterm) ≈ -3.36`), por lo que infrapronostica el 2021
excepcionalmente alto. M0, que arrastra la tasa 2015, resulta más cercano. No se
fabricó una mejora: se comunica que la referencia gana (Spec §7).

El candidato M1 (ajustado sobre 2015/2018 para la selección) tiene:

| Feature | Coeficiente |
|---|---:|
| `same_type_abstention_pct` | 5.678 |
| `previous_abstention_pct` | 1.796 |
| `previous_young_share` | −1.136 |
| `previous_senior_share` | −2.807 |
| `previous_rural_share` | −0.823 |
| `is_midterm` | −3.362 |
| `intercept` | 36.332 |

Los parámetros completos del escalador y los coeficientes se guardan en
`model.json` (sección `candidate_m1`). La explicación del modelo desplegado M0 es
la propia tasa de referencia; no requiere intercepto ni coeficientes.

## Explicación aditiva (cuando aplica)

Para M1, la predicción en la escala transformada es

`y = intercepto + Σ_j coeficiente_j · (x_j − media_j) / escala_j`.

La suma previa al recorte es el valor sin recortar; si se recorta, se documenta
que la suma corresponde al valor pre-recorte. `model.json` conserva intercepto,
medias/escalas, coeficientes y las salidas pre-recorte de 2027.

> **Cautela no causal.** Los coeficientes son asociaciones sobre agregados
> municipales; no admiten lectura causal. Pesos iguales por municipio; el LN no se
> interpreta como tamaño de una muestra binomial independiente.

## Artefactos (sin pickle/joblib)

| Archivo | Contenido |
|---|---|
| `model.json` | familia, features, `alpha`, intercepto/coeficientes/escalador, salidas pre-recorte, frecuencia de recorte. |
| `evaluation.json` | MAE/RMSE/sesgo/MAE ponderado, cohortes, exclusiones, cobertura, M0/M1 por 2021/2024, banda. |
| `predictions-2027.parquet` | 125 registros (incl. insuficientes), nunca cero sustitutivo. |
| `exclusions.csv` | municipios excluidos de 2027 con motivos. |
| `manifest.json` | hashes, versiones, fechas, limitaciones, hash lógico. |

Escritura atómica (temporal + `os.replace`); `model_run_id` es `uuid5`
determinista sobre el contenido, no un UUID aleatorio.

## Limitaciones

- Identidad `verified_catalogue` **no** prueba igualdad histórica de límites
  (`footprint_status=not_verified`); la serie se describe sobre la referencia 2025.
- Cobertura parcial por calidad (85 de 125 municipios en 2027); la selección por
  calidad introduce un sesgo de cobertura documentado en `validation.md`.
- Sólo tres elecciones de cada tipo; dependencia espacial y cambio de distribución.
- El modelo estima abstención municipal agregada, no probabilidad individual.
