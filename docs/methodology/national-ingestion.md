# Ingestión nacional CCPC

La carga nacional consume `data/raw/ccpc-national/ccpc-{año}.zip` para los años
2009, 2012, 2015, 2018, 2021 y 2024. El lector abre los ZIP directamente, usa
`csv.reader` (incluidos campos de Oaxaca con comas entrecomilladas) y procesa un
CSV/fila a la vez. Verifica los 32 CSV y el encabezado exacto de 16 columnas,
tipos/códigos, clave analítica única y `LN = SV + NV + NS`; cualquier incumplimiento
detiene la carga. No se extraen los CSV completos ni se corrigen valores fuente.

`data/sources-national.json` es el inventario autoritativo: URL, nombre local,
Last-Modified, fecha de recuperación, prefijo/directorio y los 32 sufijos de
miembro esperados. La carga verifica el SHA-256 si el inventario incluye uno; de
lo contrario calcula y registra el SHA-256 del ZIP. No descarga archivos en red.
Los nombres esperados se comparan exactamente con los 32 miembros CSV hallados,
y la carga además verifica 32 valores `EDOCVE` distintos (uno por CSV).

`EDOCVE`, `MPIOCVE` y `DEF` se normalizan a 2, 3 y 2 dígitos. Las columnas
`source_state_code`, `source_municipality_code` y `source_district` retienen sus
representaciones originales; `source_row` es el número de fila en el miembro y
`source_hash` su SHA-256. `dataset_version_id` es determinista por entidad, año y
SHA de ese CSV. La tabla `fact_ccpc_section` conserva ese grano y se particiona
por año. `DEF` se guarda como `district_2021` para 2009–2021 y `district_2023`
para 2024; un campo vacío permanece `NULL`. No se reconstruyen distritos en esta
tarea.

Cada ingesta se escribe primero en un directorio privado de staging. Sólo cuando
los seis Parquet seccionales, `municipal-observations.csv`/`.parquet` y
`national-ingest.json` con SHA-256/bytes de cada artefacto están completos se
renombra a `generations/<generation_id>/`; después `current.json` se reemplaza
atómicamente como el único punto de publicación. Una generación fallida no cambia
el puntero anterior. Los consumidores deben resolver `current.json`; el CLI y el
loader DB hacen esto automáticamente. El manifiesto de generación registra URL,
hash computado del ZIP, SHA de cada CSV, miembro, fechas fuente, conteos y
versiones. Mismo inventario y datos producen la misma generación y hashes.

Agregación municipal suma LN/SV/NV/NS antes de calcular composición demográfica.
Las participaciones joven (18–29), senior (60+) y rural se dividen entre LN. Una
observación es elegible para la regla de calidad sólo si `SV+NV >= 1000` y
`NS/LN <= 0.10`; las razones quedan explícitas. Los municipios sin filas en un
año no se convierten en cero ni se inventan observaciones.

Ejecutar después de aplicar migraciones:

```bash
python -m participa_geo.cli ingest-national \
  --source-dir data/raw/ccpc-national \
  --output-dir data/processed/national \
  --sources data/sources-national.json
```

El comando valida/genera los artefactos, luego reemplaza los hechos nacionales
dentro de una transacción PostgreSQL con `COPY` por lotes. Ante fallo del `COPY`,
la transacción restaura el contenido anterior de la tabla. La distribución de
2024 registra 300 distritos; no es una reconstrucción temporal ni asigna
territorios a partir de municipios.
