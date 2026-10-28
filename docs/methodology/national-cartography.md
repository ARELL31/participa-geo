# Cartografía nacional y servicios GIS

Las capas nacionales usan los ZIP MGS del corte **15 de diciembre de 2025**. El
import registra el SHA-256 por ZIP, EPSG UTM declarado por entidad, el corte,
provenance y la geometría transformada realmente a EPSG:4326. ENTIDAD,
MUNICIPIO, DISTRITO_FEDERAL y SECCION se validan antes de persistir: no se
aceptan capas vacías, geometrías nulas, vacías o inválidas y no se reparan
silenciosamente.

Las tablas `geo_state`, `geo_municipality`, `geo_district_2023` y `geo_section`
guardan la geometría completa para operaciones cartográficas y futuras fichas.
GeoServer sirve las vistas `*_national_view`, que aplican
`ST_SimplifyPreserveTopology(geom, 0.005)` en coordenadas geográficas (aprox.
500 m de tolerancia latitudinal en México) para el mapa de escala nacional. La
simplificación preserva topología; no sustituye ni altera las tablas fuente.

`districts_2023` identifica el marco cartográfico DERFE 2023 observado en MGS
2025 y los límites usados por la observación 2024. Sus etiquetas son del
catálogo oficial de cabeceras `district-headquarters.txt`; esta capa no representa
predicciones, escenarios ni un modelo distrital.

`bridge_municipality_district` y `bridge_section_district` son los productos
validados de Task 3 y no se reconstruyen a partir de un distrito dominante. El
puente contiene 2,581 pares y 72 municipios divididos.

GeoServer usa el workspace nacional `participa_geo_national` para no reemplazar
la capa heredada del workspace `participa_geo`. El gateway sólo permite WFS
acotado por `state_code` o `bbox`, valida niveles y limita `count` a 1,000.
WFS-T se fija en nivel BASIC; las rutas REST/admin no pertenecen al gateway. WMS
permite mapas nacionales completos.
