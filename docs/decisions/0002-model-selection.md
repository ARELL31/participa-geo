# ADR 0002 — Selección de modelo: M0 (referencia) sobre M1 (Ridge)

- Fecha: 2026-10-26
- Estado: aceptada (resultado de la validación temporal sobre datos reales)
- Alcance: T4; T5/T8 consumen la familia y las métricas.

## Contexto

Para estimar la abstención municipal 2027 se comparan dos familias sobre la
cohorte común: M0 (tasa del mismo municipio y mismo tipo en `t-6`) y M1
(`StandardScaler` + `Ridge(alpha=1.0)` con seis predictores, incluida
sociodemografía agregada). La regla de selección es fija y a priori (Spec §7):
ajuste sobre 2015/2018, validación sobre 2021, M1 se elige sólo si reduce el MAE
municipal en 2021; en empate permanece M0. Sin búsqueda de hiperparámetros ni
selección de variables sobre el test.

## Decisión

Se elige **M0**. Sobre la validación 2021:

| Modelo | MAE 2021 | RMSE 2021 | Sesgo 2021 |
|---|---:|---:|---:|
| M0 | **4.934** | 5.653 | −4.720 |
| M1 | 8.900 | 9.466 | −8.900 |

`MAE2021(M1) > MAE2021(M0)`, por lo que la referencia gana de forma honesta; no
se fabricó una mejora ni se relajaron umbrales. M1 aprende de 2015 (intermedia) y
2018 (presidencial) que las intermedias tienden a menor abstención
(`coef(is_midterm) ≈ −3.36`) e infrapronostica el 2021 excepcionalmente alto;
M0, que arrastra la tasa 2015, queda más cerca.

La evaluación 2024 (presidencial, congelada tras la elección) es coherente: M0
MAE 3.432 frente a M1 4.817. 2024 no se usó para cambiar la familia.

## Consecuencias

- Se publican **ambos** modelos y métricas (2021 y 2024), incluido el candidato
  con sociodemografía aunque se despliegue M0 (Spec §7). `model.json` conserva
  `candidate_m1` con intercepto, coeficientes y escalador.
- La explicación del modelo desplegado es la propia tasa de referencia (`t-6`),
  sin coeficientes; la cautela no causal rige igualmente.
- La banda de incertidumbre usa los errores de la familia elegida (M0) en 2021.
- No se interpretan los coeficientes de M1 como efectos causales.

## Alternativas consideradas

- **Forzar M1 por su explicabilidad**: rechazada; la regla de selección es a
  priori y el MAE de M1 es claramente peor en 2021. Publicar M1 como ganador
  ocultaría un resultado desfavorable.
- **Ajustar `alpha` o variables para mejorar M1 en 2021**: rechazada; sería
  sintonizar sobre el test y viola Spec §7.
