# Validación temporal y métricas — modelo de abstención

Fecha: 2026-10-26. Alcance: T4. Todas las cifras son **computadas** sobre los
datos reales de Jalisco (`data/processed`), no fijadas a mano.

## Esquema temporal (Spec §7, decisión del controlador)

| Uso | Objetivos de ajuste | Antecedentes | Año predicho |
|---|---|---|---|
| Validación y elección M0/M1 | 2015 y 2018 | t-6, t-3 por objetivo | **2021** |
| Evaluación final | 2015, 2018 y 2021 | misma regla | **2024** |
| Ajuste final de la familia elegida | 2015, 2018, 2021 y 2024 | misma regla | **2027** |

- M1 se elige **sólo** si reduce el MAE municipal en 2021; en empate permanece M0.
- 2024 se evalúa **después** de congelar la familia; nunca cambia familia,
  variables, `alpha` ni umbrales. Se publican ambos modelos en ambos cortes.
- El escalador se ajusta sólo con entrenamiento; sin búsqueda de hiperparámetros.
- Los pronósticos se recortan a `[0, 100]` y se evalúan igual que se sirven.

## Cohorte y cobertura (municipios y LN)

| Objetivo | Elegibles | Excluidos | LN elegible | LN total | Cobertura LN |
|---|---:|---:|---:|---:|---:|
| 2015 | 116 | 9 | 5 094 357 | 5 513 033 | 92.4 % |
| 2018 | 105 | 20 | 5 170 301 | 5 904 226 | 87.6 % |
| 2021 | 91 | 34 | 5 212 679 | 6 214 764 | 83.9 % |
| 2024 | 75 | 50 | 5 227 537 | 6 619 379 | 79.0 % |
| 2027 | **85** | **40** | 6 054 287* | 6 619 379* | 91.5 %* |

\* Para 2027 no hay LN observado; la cobertura se expresa sobre la base del último
antecedente (2024). El conteo de 85 candidatos se obtiene de aplicar la regla de
calidad + identidad (`verified_catalogue`), no de una constante; coincide con la
expectativa preliminar del diseño porque T3 no redujo la cohorte (los 125
corresponden a `verified_catalogue`/`not_verified`).

Todas las exclusiones de 2027 son por `high_unknown_share` (ninguna por identidad
ambigua o cambio administrativo documentado). Se conservan los 125 municipios en
las tablas; la exclusión afecta entrenamiento/evaluación/estimación, no borra
datos observados.

## Métricas (puntos porcentuales)

Evaluación de selección — **2021** (intermedia):

| Modelo | n | MAE | RMSE | Sesgo | MAE ponderado |
|---|---:|---:|---:|---:|---:|
| M0 | 91 | **4.934** | 5.653 | −4.720 | 3.802 |
| M1 | 91 | 8.900 | 9.466 | −8.900 | 6.350 |

Evaluación congelada — **2024** (presidencial):

| Modelo | n | MAE | RMSE | Sesgo | MAE ponderado |
|---|---:|---:|---:|---:|---:|
| M0 | 75 | 3.432 | 4.532 | −3.042 | 1.393 |
| M1 | 75 | 4.817 | 5.959 | 2.180 | 10.762 |

El MAE ponderado pondera por el denominador conocido (`SV + NV`) del objetivo; es
un indicador secundario. El MAE ponderado de M1 en 2024 (10.76 frente a 4.82 sin
ponderar) revela que los municipios grandes concentran el error de M1.

**Selección**: `MAE2021(M1)=8.900 > MAE2021(M0)=4.934`, luego **M0**. No hay
empate; no se forzó una mejora. Los sesgos negativos de M0 (−4.72 en 2021,
−3.04 en 2024) reflejan que la tasa de `t-6` subestima ambos objetivos.

## Banda de incertidumbre

- Amplitud = percentil 90 del error absoluto de la familia elegida (M0) en 2021:
  **8.562 pp** (n = 91 errores elegibles ≥ 30).
- Banda simétrica recortada a `[0, 100]`; se etiqueta **rango de error histórico
  de referencia**, nunca “90 % de confianza”.
- `risk_unstable = True` cuando la banda cruza un umbral (40 o 50). Con esta
  amplitud, **70 de 85** municipios elegibles tienen categoría inestable.
- Cobertura empírica fuera de tiempo: al comparar la banda congelada con los
  errores absolutos de 2024, **71 de 75 (94.7 %)** quedan dentro de la amplitud.
  Es una comprobación descriptiva; 2024 no ajusta la banda ni la selección.
- No se promete cobertura futura del 90 %: pocos ciclos, dependencia espacial y
  cambio de distribución limitan la interpretación (Spec §8).

## Semáforo 2027 (85 elegibles)

| Riesgo | Municipios |
|---|---:|
| Bajo (< 40) | 36 |
| Medio (40 – < 50) | 27 |
| Alto (≥ 50) | 22 |
| Insuficiente | 40 |

El semáforo es analítico, no una clasificación oficial del INE. Los 40
insuficientes conservan `estimated_abstention_pct = null` (nunca cero).

## Reproducibilidad

- Dos ajustes sobre los mismos datos y locks producen la misma familia, el mismo
  `model_run_id`, los mismos IDs/exclusiones y valores idénticos con
  `rtol=0, atol=1e-8` (verificado por `tests/integration/test_training.py`).
- El hash lógico del manifiesto excluye la marca de tiempo.
- Mutar el objetivo 2024 **no** cambia la elección hecha en 2021 (la familia se
  elige sólo con 2021), aunque sí cambia el test y el ajuste final.

## Limitaciones

- Retrospectiva por año de referencia (no reproducción de pronóstico operativo)
  al no documentarse las fechas de publicación de los CCPC.
- La prueba final 2024 es presidencial, lo que limita su transferencia a la
  intermedia 2027; se destacan por separado los resultados intermedios de 2021.
