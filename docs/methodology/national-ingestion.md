# Ingestión nacional CCPC

La carga nacional consume `data/raw/ccpc-national/ccpc-{año}.zip` para los años
2009, 2012, 2015, 2018, 2021 y 2024. El lector abre los ZIP directamente, usa
`csv.reader` (incluidos campos de Oaxaca con comas entrecomilladas) y procesa un
CSV/fila a la vez. Verifica los 32 CSV y el encabezado exacto de 16 columnas,
tipos/códigos, clave analítica única y `LN = SV + NV + NS`; cualquier incumplimiento
detiene la carga. No se extraen los CSV completos ni se corrigen valores fuente.

`EDOCVE`, `MPIOCVE` y `DEF` se normalizan a 2, 3 y 2 dígitos. Las columnas
`source_state_code`, `source_municipality_code` y `source_district` retienen sus
representaciones originales; `source_row` es el número de fila en el miembro y
`source_hash` su SHA-256. `dataset_version_id` es determinista por entidad, año y
SHA de ese CSV. La tabla `fact_ccpc_section` conserva ese grano y se particiona
por año. `DEF` se guarda como `district_2021` para 2009–2021 y `district_2023`
para 2024; un campo vacío permanece `NULL`. No se reconstruyen distritos en esta
tarea.

La salida procesada contiene `ccpc-section-{año}.parquet`, agregados
`municipal-observations.csv` y `national-ingest.json`. El manifiesto registra URL,
SHA-256 del ZIP, SHA-256 de cada CSV, miembro, fecha Last-Modified publicada por
la auditoría, conteos y versiones. Las salidas se escriben con reemplazo atómico.
El manifiesto es determinista para facilitar comprobaciones de idempotencia.

Agregación municipal suma LN/SV/NV/NS antes de calcular composición demográfica.
Las participaciones joven (18–29), senior (60+) y rural se dividen entre LN. Una
observación es elegible para la regla de calidad sólo si `SV+NV >= 1000` y
`NS/LN <= 0.10`; las razones quedan explícitas. Los municipios sin filas en un
año no se convierten en cero ni se inventan observaciones.

Ejecutar después de aplicar migraciones:

```bash
python -m participa_geo.cli ingest-national \
  --source-dir data/raw/ccpc-national \
  --output-dir data/processed/national
```

El comando valida/genera los artefactos, luego reemplaza los hechos nacionales
dentro de una transacción PostgreSQL con `COPY` por lotes. Ante fallo del `COPY`,
la transacción restaura el contenido anterior de la tabla. La distribución de
2024 registra 300 distritos; no es una reconstrucción temporal ni asigna
territorios a partir de municipios.
