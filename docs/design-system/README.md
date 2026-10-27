# Sistema de diseño de PARTICIPA-GEO

Este documento fija la dirección visual y los tokens del MVP. No sustituye la
paleta aprobada ni introduce un tema oscuro. La implementación vive en
`apps/web/src/styles/tokens.css` y `apps/web/src/styles/app.css`.

## Dirección

Plataforma gubernamental de analítica geoespacial: sobria, densa y precisa. Sin
apariencia de landing comercial, sin degradados decorativos, sin glassmorphism y
sin emojis. La jerarquía se construye con tipografía, bordes discretos y espacio
en blanco.

- Shell persistente: sidebar de 256 px, header de 64 px, contenido máximo de
  1440 px con gutters de 32 px en escritorio y 16 px en móvil.
- Sidebar colapsable: en móvil se abre con Radix Dialog, atrapa el foco y lo
  devuelve al botón que abrió el menú.
- Rutas: `/` (Panel ejecutivo), `/territory` (Inteligencia territorial),
  `/prediction`, `/scenarios`, `/reports`. Los módulos aún no entregados muestran
  “Pendiente” y no exponen controles o enlaces de acción falsos.
- El año objetivo 2027 es fijo y aparece separado del filtro histórico.

## Paleta

| Token | Valor | Uso |
|---|---|---|
| `--color-primary` | `#6F1739` | navegación, acciones primarias, línea histórica |
| `--color-primary-hover` | `#54102A` | hover de navegación y acciones primarias |
| `--color-secondary` | `#8B1E3F` | módulo activo, acentos de estructura |
| `--color-accent` | `#AD536D` | avisos, guía del año seleccionado, riesgo medio |
| `--color-background` | `#F7F6F5` | fondo de aplicación |
| `--color-surface` | `#FFFFFF` | tarjetas y superficies |
| `--color-text` | `#252525` | texto normal |
| `--color-text-secondary` | `#666666` | texto secundario y ayudas |
| `--color-border` | `#E6E0E2` | divisores y bordes discretos |
| `--color-control` | `#666666` | borde de controles (no es un color nuevo de marca) |

`--color-control` reutiliza el gris secundario aprobado porque el borde
`#E6E0E2` no alcanza 3:1 sobre blanco para delimitar un control. No se añadió
ningún color de marca.

## Tipografía y escala

Inter local vía `@fontsource/inter` (pesos 400/500/600/700), sin CDN ni descarga
en tiempo de ejecución. Licencia SIL Open Font License 1.1; el archivo de licencia
se copia a `/licenses/inter-OFL.txt` en la imagen web.

- Base 16 px; cuerpo con línea 1.5.
- Escala: 12, 14, 16, 20, 24, 28–32 px. H1 fluido 28–32 px; H2 24 px; H3 20 px.
- Títulos con línea 1.25 y peso 600; cifras KPI 24–32 px con números tabulares.

## Espaciado, radios y bordes

- Escala 4/8: 4, 8, 12, 16, 24, 32, 48 px (`--space-1` … `--space-12`).
- Bordes de 1 px. Radios de 4–6 px; nunca píldoras.
- Sin sombras decorativas: las tarjetas se separan por superficie y borde.

## Foco y contraste

- Anillo de foco visible de 2 px con offset de 2 px. Nunca se elimina el outline
  sin reemplazo.
- Sobre superficies claras el anillo usa `#252525`; sobre la sidebar/diálogo usa
  `#FFFFFF`, ambos con contraste mayor a 3:1.
- `scroll-padding-top` y header sticky evitan que el foco quede oculto.

Contrastes calculados (WCAG 2.x, sRGB):

| Combinación | Ratio | Resultado |
|---|---:|---|
| `#252525` sobre `#F7F6F5` | 14.20:1 | texto normal AA/AAA |
| `#666666` sobre `#FFFFFF` | 5.74:1 | texto normal AA |
| `#666666` sobre `#F7F6F5` | 5.32:1 | texto normal AA |
| `#6F1739` sobre `#FFFFFF` | 11.31:1 | texto/enlace AA/AAA |
| `#FFFFFF` sobre `#6F1739` | 11.31:1 | navegación AA/AAA |
| `#FFFFFF` sobre `#8B1E3F` | 8.92:1 | módulo activo AA/AAA |
| `#FFFFFF` sobre `#AD536D` | 4.96:1 | etiqueta de riesgo medio AA |
| `#252525` sobre `#FFFFFF` (foco) | 15.91:1 | indicador de foco >3:1 |
| `#FFFFFF` sobre `#6F1739` (foco) | 11.31:1 | indicador de foco >3:1 |

No se declara conformidad WCAG AA completa. Las verificaciones realizadas y las
no realizadas se registran en el reporte de la tarea.

## Componentes

- **PageState**: carga, error, vacío y pendiente con texto explícito, sin cifras
  de ejemplo. Los errores usan `role="alert"`.
- **DataTable**: caption, encabezados `scope="col"`, contenedor desplazable
  enfocable, fila vacía explícita y números tabulares.
- **GeographyNotice**: aviso permanente de la referencia INE 15DIC2025, en
  `role="note"`, no descartable.
- **RiskBadge**: etiqueta textual e icono; el gris “Insuficiente” nunca se
  presenta como verde ni como cero.
- **HistoryChart**: SVG simple con línea de abstención, puntos del año
  seleccionado, quiebres cuando falta un dato y tabla de seis años equivalente.
- **MunicipalMap**: WMS raster vía gateway, interacción WFS y tabla alternativa
  siempre disponible; si MapLibre o la capa fallan, la tabla se abre y el error
  queda visible.

## Estados y datos ausentes

- Una tasa nula se muestra como “No disponible” o “Información insuficiente”;
  nunca se sustituye por 0.
- Los filtros se serializan en la URL (`territory_id`, `year`). Un año distinto
  de 2009/2012/2015/2018/2021/2024 produce `RangeError`; el shell ofrece
  “Restablecer filtros” en lugar de una página en blanco.
- Los resultados se cachean por filtros y usan `AbortSignal`; una respuesta
  antigua no puede reemplazar la selección vigente.

## Responsive y movimiento

- Layouts diseñados para 320, 375, 768, 1024 y 1440 px. La suite Playwright
  verifica 320, 375 y 1440; 768 y 1024 se revisan por CSS, no de forma
  automatizada.
- La prueba de 200% usa 640 px de viewport con `zoom: 2` como aproximación; no
  sustituye una comprobación manual del zoom del navegador.
- Objetivos táctiles de al menos 44 px en móvil.
- `prefers-reduced-motion` desactiva animaciones y transiciones en CSS; el único
  movimiento es el indicador de carga. Esta regla se revisó en CSS, no con una
  prueba automatizada de movimiento reducido.

## Verificaciones registradas (T7, 26 de octubre de 2026)

Ejecutadas dentro de Docker:

- Vitest/RTL: 16 pruebas (filtros de URL, shell, foco móvil, datos nulos,
  respuesta tardía con `AbortSignal`, aviso geográfico y alternativa tabular).
- Playwright/Chromium: 8 pruebas contra la API real por el proxy web; municipio y
  año actualizan KPI y tabla, navegación Tab/Enter, sidebar móvil 375 px con
  retorno de foco, layout 1440 px, reflujo 320 px, aproximación de zoom 200 %,
  WMS/WFS reales y fallo de WMS con tabla disponible.
- `npm run typecheck` y `npm run build` en el contenedor Node 24.
- Contraste calculado con la fórmula WCAG 2.x para todas las combinaciones de la
  tabla anterior.

No se ejecutó axe, no se probó con lectores de pantalla, no se automatizó
`prefers-reduced-motion`, no se probó el zoom real del navegador ni los anchos
768/1024 de forma automatizada. Por ello **no se declara conformidad WCAG AA
completa**; estas comprobaciones quedan como apoyo y deuda explícita.
