# Evidencia de investigación — PARTICIPA-GEO

Investigación y decisiones de la fase 0. Fecha de sesión original: 2026-10-26.
Estado posterior: MVP implementado, verificado y empaquetado; ver
`docs/hackathon/verification-results.md`.

## Datos

- Inventario de los seis ZIP nacionales: `docs/methodology/evidence/ccpc-inventory.json`.
- CSV íntegros de Jalisco, obtenidos como miembros de ZIP mediante HTTP Range:
  `data/raw/ccpc/jalisco-{año}.csv` (almacenamiento ignorado por Git; incluidos
  en el ZIP técnico con confirmación del usuario).
- Perfil por año/municipio y SHA-256: `docs/methodology/evidence/jalisco-audit.json`.
- Universo leído: 2,999,641 filas agregadas de 125 códigos municipales presentes
  en los seis años.
- Identidad `LN = SV + NV + NS` observada en todas las filas; no se observaron
  negativos ni duplicados de la clave analizada.
- Faltante localizado: `DEL` en 2,953 filas de 2024. No se imputó.
- `NS/LN` varía mucho entre municipios: las medias estatales no bastan para
  aprobar calidad territorial.
- El MVP final sí estimó un modelo y ejecutó PostGIS/GeoServer; esta sección
  conserva la evidencia de la investigación inicial.

## Cartografía

- ZIP oficial INE:
  `https://cartografia.ine.mx/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/14.zip`.
- Descarga original conservada como
  `data/raw/gis/ine-jalisco-2025-12-15.zip`; incluye `MUNICIPIO.shp` y
  auxiliares, con EPSG:32613 declarado.
- Se comprobó la coincidencia de 125 claves y nombres DBF frente a cada uno de
  los seis CSV.
- No se verificaron topología ni igualdad de límites históricos. Mayo 2023 no
  fue localizado en los mecanismos consultados.
- Correspondencia INE–INEGI por nombres normalizados: derivada, no oficial ni
  geométrica; 90/125 claves difieren. No es dependencia del MVP.

## Herramientas

AlmaLinux 10.2, kernel WSL2, systemd, x86_64, ~8 GB RAM. Python 3.12.15 y
Git 2.52.0 disponibles inicialmente. El usuario instaló Docker Engine 29.9.2 y
Compose 5.6.1; el acceso al daemon se comprobó con la membresía de grupo
existente. Las dependencias de aplicación corren en contenedores; no se
instalaron paquetes en el host desde el agente.

Documentación oficial Docker consultada: `https://docs.docker.com/engine/install/centos/`;
no declara soporte específico a AlmaLinux. Se comprobó la existencia de paquetes
EL10 y el daemon quedó operativo. No se modificaron firewall, SELinux ni permisos
del socket.

## Diseño y ejecución

- Diseño aprobado: `docs/superpowers/specs/2026-10-26-participa-geo-mvp-design.md`.
- Plan aprobado y ejecutado: `docs/superpowers/plans/2026-10-26-participa-geo-mvp.md`.
- Checklist de fase 0: `docs/superpowers/fase0-checklist.md`.
- El usuario aprobó Jalisco, horizonte intermedio 2027, referencia cartográfica
  2025 con advertencias, cobertura parcial por calidad y el repositorio
  `/home/arell31/participa-geo`.
- El usuario confirmó incluir los CSV/Shapefile originales del INE en el ZIP
  técnico con atribución, URLs y checksums.

## Resultado

El ensayo limpio desde el ZIP reprodujo familia M0, exclusiones, predicciones y
escenario con `max_abs_diff=0.0` (`atol=1e-8`). Las limitaciones metodológicas
(cartografía 2025, cobertura 85/125, banda de error histórica, M0 seleccionado y
M1 no seleccionado) están documentadas en el reporte y la interfaz.
