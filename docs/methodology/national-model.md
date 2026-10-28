# Modelo municipal nacional 2027

## Alcance y población

El único modelo predictivo nacional de esta entrega opera a nivel municipal y
estima la abstención conocida (`100 × NV / (SV + NV)`) para la elección federal
intermedia de 2027. La unidad se identifica por entidad y clave municipal INE;
no se promedian tasas ni se construyen resultados distritales a partir de
municipios. Los distritos permanecen como observación 2024 exclusivamente.

El modelo consume los agregados municipales CCPC nacionales de 2009, 2012,
2015, 2018, 2021 y 2024. Un municipio es elegible en un corte sólo si tiene
identidad explícita `verified_catalogue`, huella no marcada como cambio conocido,
observaciones requeridas, `SV + NV >= 1000` y `NS/LN <= 0.10` en cada año
requerido. Una identidad no leída o ausente es error; una ausencia, un conteo
insuficiente y una observación no elegible nunca se convierten en cero.

Para los objetivos retrospectivos se requieren `t`, `t-3` y `t-6`; para 2027
sólo se requieren 2021 y 2024. El estado y municipio forman siempre la llave,
incluyendo las exclusiones. Las identidades y sus estados de huella se cargan
desde las correspondencias de catálogo nacional en PostGIS; la ejecución valida
2,477 municipios, 32 entidades, al menos una correspondencia coherente por municipio
y estatus completos antes de entrenar. No exige que las claves municipales hayan
existido en las seis elecciones: esas ausencias se conservan como exclusiones de corte.

## Candidatos, cortes y selección

- **M0:** abstención conocida del mismo municipio y tipo de elección en `t-6`.
- **M1:** `StandardScaler` entrenado sólo con los objetivos de ajuste y Ridge con
  `alpha=1.0`; predictores: abstención del mismo tipo (`t-6`), abstención previa
  (`t-3`), shares LN 18–29, LN 60+, rural de `t-3`, indicador de elección
  intermedia y efectos fijos one-hot de entidad. La entidad 01 es referencia.
- La cohorte que se puntúa es idéntica para M0 y M1 en cada corte.
- Selección: ajustar con objetivos 2015/2018 y elegir M1 únicamente si mejora la
  MAE en 2021; un empate conserva M0.
- 2024 se evalúa tras congelar familia, variables y alpha; nunca decide el
  candidato. El ajuste M1 de prueba 2024 usa objetivos 2015/2018/2021.
- El ajuste final para 2027 usa objetivos 2015/2018/2021/2024.

Se publican MAE, RMSE, sesgo, MAE ponderado por `SV+NV` y conteo de recortes
para ambos candidatos en 2021 y 2024. Los valores predichos se limitan a 0–100.

## Incertidumbre y trazabilidad

La amplitud de banda es el P90 del error absoluto de 2021 de la familia
seleccionada; requiere al menos 30 errores. Con menos de 30 se deja sin banda.
La cobertura empírica se calcula sobre errores 2024 y se informa como cobertura
observada, no como intervalo de confianza ni garantía de cobertura futura.
Municipios no elegibles se publican con estimación y banda nulas y estado
`insufficient`.

`model_run_id` deriva de nivel, hash de agregados, identidades/huellas, cohortes,
exclusiones, cortes, candidatos, métricas, parámetros ajustados y banda. El
manifiesto contiene hashes y tamaños de los artefactos. No se serializan
objetos Python, pickle ni joblib. Salidas: `model.json`, `evaluation.json`,
`predictions-2027.parquet`, `exclusions-by-cut.csv` y `manifest.json` bajo
`data/processed/national/model/`.

Comando: `python -m participa_geo.cli train-national-municipal` (acepta
`--processed-dir` y `--output-dir`). La salida se debe generar únicamente cuando
estén disponibles agregados, cartografía/identidades nacionales y estatus de
cobertura verificables. El modelo describe asociaciones territoriales; no
infiere comportamiento individual ni efectos causales.

## Limitaciones

La huella histórica municipal no se presume idéntica a la cartografía actual.
Los shares demográficos son agregados sobre LN. Sólo hay pocas elecciones
federales temporales y existe dependencia espacial y posible cambio de
distribución; por ello la banda histórica no constituye promesa probabilística.
No se entrena ni publica modelo, predicción, banda o escenario distrital 2027.
