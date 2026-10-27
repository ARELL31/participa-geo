# Controles de calidad — Ingestión CCPC

La calidad se evalúa **después** de sumar los conteos por municipio/año, nunca
sobre tasas por celda. La regla es la aprobada en el diseño (§6): una observación
municipal/año es **elegible** cuando

- los conteos son válidos (`LN = SV + NV + NS`, no negativos), y
- `SV + NV >= 1000`, y
- `NS / LN <= 0.10`.

## Motivos estables de exclusión

| Motivo | Condición |
|---|---|
| `invalid_counts` | Conteos negativos o `LN != SV + NV + NS`. |
| `zero_denominator` | `SV + NV == 0` (denominador conocido nulo). |
| `small_known_count` | `SV + NV < 1000`. |
| `high_unknown_share` | `NS / LN > 0.10`. |

Los motivos `ambiguous_identity`, `known_administrative_change`, `missing_lag` e
`insufficient_error_history` pertenecen a tareas posteriores (T3/T4) y no se
emiten en esta etapa. Los estados geográficos (`identity_status`,
`footprint_status`) se dejan en `None` en T2; `None` **nunca** significa identidad
verificada y bloqueará la publicación de pronósticos hasta que T3 los complete.

## Resultados reales (computados, no fijados a mano)

Observaciones elegibles por año (de 125 municipios por año):

| Año | Elegibles | NS/LN estatal | Abstención conocida |
|---|---:|---:|---:|
| 2009 | 118 | 2.19 % | 48.81 % |
| 2012 | 124 | 0.13 % | 36.11 % |
| 2015 | 123 | 3.47 % | 47.95 % |
| 2018 | 108 | 6.54 % | 41.83 % |
| 2021 | 103 | 3.38 % | 52.62 % |
| 2024 | 101 | 5.87 % | 42.94 % |

Total: **677** observaciones municipales/año elegibles de 750.

Para el objetivo 2027 (que exige calidad en los antecedentes 2021 y 2024, sin
validación geográfica aún): **85 municipios** son elegibles en ambos años. Esta
cifra coincide con la expectativa preliminar del diseño (85), pero se obtiene de
aplicar la regla, no de una constante. El conteo definitivo puede bajar tras la
validación geográfica de T3.

Como verificación cruzada, la regla de cohorte común (calidad en `t`, `t-3` y
`t-6`, responsabilidad de T4) reproduce exactamente los conteos preliminares del
diseño: 116 filas para objetivo 2015, 105 para 2018, 91 para 2021 y 75 para 2024.

## Cobertura y sesgo

La selección por calidad excluye municipios pequeños o con `NS` elevado; la
cobertura se informa tanto en municipios como en `LN` (total y evaluable) en las
tareas que consumen estas observaciones. La media estatal de `NS/LN` no basta:
`NS` varía mucho entre municipios y la regla es territorial, no estatal. No se
rellena ningún territorio excluido con predicciones ficticias.

## Determinismo e idempotencia

- Verificación previa: el SHA-256 de cada CSV se compara contra
  `data/sources.json`; una discrepancia aborta la ingestión sin escribir nada.
- Escritura atómica: los tres artefactos se escriben a archivo temporal y se
  renombran (`os.replace`) al finalizar.
- Reejecución: entrada idéntica produce agregados idénticos y el mismo hash lógico
  `aggregate_sha256` (`d33ccc34…` para este corte); no se duplican claves
  `(año, municipio)`.

## Verificación de fuentes (`--fetch`)

El camino de descarga opcional (`--fetch`) usa el ZIP nacional completo como
alternativa verificada: se valida el CRC del miembro al leerlo (`zipfile`), se
comprueba el SHA-256 del CSV extraído, se rechazan rutas `..`/absolutas y se
imponen límites de tamaño (ZIP ≤ 256 MiB, miembro ≤ 96 MiB). Nunca se extraen
miembros arbitrarios. Los tests de esta tarea ingieren desde los archivos locales
verificados (`data/raw/ccpc/`), sin depender de `/tmp/opencode`.
