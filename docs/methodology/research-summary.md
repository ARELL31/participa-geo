# Evidencia de investigación — PARTICIPA-GEO

Investigación, no implementación ni pruebas de producto. Fecha de sesión: 2026-10-26.

## Datos

- Inventario de los seis ZIP nacionales: `/tmp/opencode/participa-geo-ccpc-inventory.json`.
- CSV íntegros de Jalisco, obtenidos como miembros de ZIP mediante HTTP Range: `/tmp/opencode/participa-geo-data-research/jalisco-{año}.csv`.
- Perfil por año/municipio y SHA-256: `/tmp/opencode/participa-geo-data-research/jalisco-audit.json`.
- Universo leído: 2999641 filas agregadas de 125 códigos municipales presentes en los seis años.
- Identidad LN=SV+NV+NS observada en todas las filas; no se observaron negativos ni duplicados de la clave analizada.
- Faltante localizado: DEL en 2953 filas de 2024. No se imputó.
- NS/LN varía mucho entre municipios: las medias estatales no bastan para aprobar calidad territorial.
- No se estimaron modelos ni se ejecutó infraestructura GIS.

## Cartografía

- Agente GIS independiente consultó APIs/JS públicos oficiales; sus archivos están en `/tmp/opencode/participa-geo-gis/`.
- ZIP oficial INE: `https://cartografia.ine.mx/mapoteca/MGS_UTM_SHAPEFILE_15DIC2025/14.zip`.
- Descarga original local: `verified-4.dat`; incluye MUNICIPIO.shp y auxiliares, EPSG:32613 declarado.
- Se comprobó nuevamente en sesión principal la coincidencia de 125 claves y nombres DBF frente a cada uno de los seis CSV.
- No se verificaron topología ni igualdad de límites históricos. Mayo2023 no fue localizado en los mecanismos consultados.
- Correspondencia INE–INEGI por nombres normalizados: derivada, no oficial ni geométrica; 90/125 claves difieren. No es dependencia del MVP.

## Herramientas

AlmaLinux10.2, kernelWSL2, systemd, x86_64, ~8GBRAM. Python3.12.15 y Git2.52.0 disponibles. Docker, Node/npm y bibliotecas científicas no encontrados en el PATH/Python global inspeccionados. No se ha instalado nada ni cambiado configuración del sistema.

Documentación oficial Docker consultada: `https://docs.docker.com/engine/install/centos/`; cubre CentOSStream10/9, no declara soporte específico a AlmaLinux. Se comprobó existencia de paquetesEL10 en `https://download.docker.com/linux/centos/10/x86_64/stable/Packages/`. DockerDesktop con integraciónWSL es otra alternativa si ya existe en el host; mecanismo pendiente de confirmación.

## Diseño

Borrador sujeto a aprobación: `/tmp/opencode/participa-geo-2026-10-26-design.md`.
Checklist: `/tmp/opencode/participa-geo-fase0-checklist.md`.

Actualización posterior a la investigación: el usuario aprobó Jalisco, horizonte intermedio2027, referencia geográfica2025 con advertencias, cobertura parcial por calidad y repositorio `/home/arell31/participa-geo`. Docker quedó instalado por el usuario y se comprobó acceso al daemon mediante la membresía de grupo existente. El diseño aprobado se conserva en `docs/superpowers/specs/2026-10-26-participa-geo-mvp-design.md`; el plan técnico en `docs/superpowers/plans/2026-10-26-participa-geo-mvp.md` está pendiente de aprobación.
