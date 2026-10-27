"""Institutional PDFs: 12-page methodology report, 9-slide executive deck and
the scenario PDF. All numbers come from :class:`DeliveryContext`; no page is
filled with invented results.
"""

from __future__ import annotations

import io
from datetime import UTC
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from participa_geo.api.schemas.common import DatasetMeta
from participa_geo.api.schemas.scenarios import ScenarioDTO
from participa_geo.reporting.delivery import DeliveryContext, repo_root

PRIMARY = colors.HexColor("#6F1739")
SECONDARY = colors.HexColor("#8B1E3F")
ACCENT = colors.HexColor("#AD536D")
TEXT = colors.HexColor("#252525")
MUTED = colors.HexColor("#666666")
BORDER = colors.HexColor("#E6E0E2")
SURFACE = colors.HexColor("#FFFFFF")
BACKGROUND = colors.HexColor("#F7F6F5")
WARNING_BG = colors.HexColor("#F4E6EB")
LOW = colors.HexColor("#2E7D32")
MEDIUM = colors.HexColor("#F9A825")
HIGH = colors.HexColor("#C62828")
INSUFFICIENT = colors.HexColor("#9E9E9E")

FONT_REGULAR = "Inter"
FONT_BOLD = "InterSemiBold"


def _font_dir() -> Path:
    return repo_root() / "docs" / "hackathon" / "fonts"


def _register_fonts() -> tuple[str, str]:
    regular = _font_dir() / "Inter-Regular.ttf"
    bold = _font_dir() / "Inter-SemiBold.ttf"
    if regular.is_file():
        if FONT_REGULAR not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
        if bold.is_file() and FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
        pdfmetrics.registerFontFamily(
            FONT_REGULAR,
            normal=FONT_REGULAR,
            bold=FONT_BOLD if bold.is_file() else FONT_REGULAR,
            italic=FONT_REGULAR,
            boldItalic=FONT_BOLD if bold.is_file() else FONT_REGULAR,
        )
        return FONT_REGULAR, FONT_BOLD if bold.is_file() else FONT_REGULAR
    # A missing optional font must never block the institutional report; the
    # fallback is the built-in Helvetica and the license note remains explicit.
    return "Helvetica", "Helvetica-Bold"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    regular, bold = _register_fonts()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName=bold,
            fontSize=30,
            leading=35,
            textColor=PRIMARY,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName=regular,
            fontSize=13,
            leading=19,
            textColor=MUTED,
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=20,
            leading=25,
            textColor=PRIMARY,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=13,
            leading=17,
            textColor=SECONDARY,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.6,
            leading=13.6,
            textColor=TEXT,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8,
            leading=11,
            textColor=MUTED,
            spaceAfter=3,
        ),
        "metric": ParagraphStyle(
            "Metric",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=17,
            leading=20,
            textColor=PRIMARY,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=7.5,
            leading=9.5,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=7.6,
            leading=9.6,
            textColor=TEXT,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=7.6,
            leading=9.6,
            textColor=colors.white,
        ),
        "slide_title": ParagraphStyle(
            "SlideTitle",
            parent=base["Title"],
            fontName=bold,
            fontSize=28,
            leading=32,
            textColor=PRIMARY,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "slide_body": ParagraphStyle(
            "SlideBody",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=13,
            leading=19,
            textColor=TEXT,
            spaceAfter=7,
        ),
        "slide_metric": ParagraphStyle(
            "SlideMetric",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=25,
            leading=28,
            textColor=PRIMARY,
            alignment=TA_CENTER,
        ),
        "slide_metric_label": ParagraphStyle(
            "SlideMetricLabel",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9,
            leading=12,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "sin estimación"
    return f"{value:.{digits}f} %"


def _pp(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f} pp"


def _table(
    rows: list[list[Any]],
    *,
    widths: list[float] | None = None,
    header: bool = True,
    font_size: float = 7.6,
    highlight_first_col: bool = False,
) -> Table:
    styles = _styles()
    data = [
        [
            Paragraph(str(cell), styles["table_header" if header and index == 0 else "table_cell"])
            for cell in row
        ]
        for index, row in enumerate(rows)
    ]
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), PRIMARY))
    if highlight_first_col:
        commands.append(("BACKGROUND", (0, 1), (0, -1), WARNING_BG))
    for index in range(1 if header else 0, len(rows)):
        if index % 2 == 0:
            commands.append(("BACKGROUND", (0, index), (-1, index), BACKGROUND))
    table.setStyle(TableStyle(commands))
    return table


def _metric_box(value: str, label: str, *, width: float = 42 * mm) -> Table:
    styles = _styles()
    table = Table(
        [[Paragraph(value, styles["metric"])], [Paragraph(label, styles["metric_label"])]],
        colWidths=[width],
        rowHeights=[11 * mm, 9 * mm],
        hAlign="CENTER",
    )
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _warning(text: str) -> Table:
    styles = _styles()
    table = Table([[Paragraph(text, styles["body"])]], colWidths=[170 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WARNING_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _page_decorator(report_title: str, *, landscape_mode: bool = False):
    def decorate(canvas: pdf_canvas.Canvas, doc) -> None:
        regular, _ = _register_fonts()
        canvas.saveState()
        width, height = landscape(A4) if landscape_mode else A4
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, height - 13 * mm, width - 18 * mm, height - 13 * mm)
        canvas.setFont(regular, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, height - 10.5 * mm, report_title)
        canvas.drawRightString(
            width - 18 * mm,
            height - 10.5 * mm,
            "PARTICIPA-GEO · Jalisco 2009–2027 · uso local",
        )
        canvas.line(18 * mm, 12 * mm, width - 18 * mm, 12 * mm)
        canvas.drawString(
            18 * mm,
            8 * mm,
            "Agregados municipales. Prohibida la inferencia individual. "
            "Los escenarios no implican efecto causal.",
        )
        canvas.drawRightString(width - 18 * mm, 8 * mm, f"Página {doc.page}")
        canvas.restoreState()

    return decorate


def _document(
    buffer: io.BytesIO,
    *,
    title: str,
    pagesize=A4,
    landscape_mode: bool = False,
):
    return SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="PARTICIPA-GEO",
        subject="Análisis municipal de participación electoral, Jalisco",
        creator="PARTICIPA-GEO",
    )


def generate_methodology(context: DeliveryContext) -> bytes:
    """Generate the reviewed 12-page methodology report (accepted 10–15)."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = _document(buffer, title="Reporte metodológico PARTICIPA-GEO")
    doc.build(
        _methodology_story(context, styles),
        onFirstPage=_page_decorator("Reporte metodológico · PARTICIPA-GEO"),
        onLaterPages=_page_decorator("Reporte metodológico · PARTICIPA-GEO"),
    )
    return buffer.getvalue()


def _methodology_story(context: DeliveryContext, styles: dict[str, ParagraphStyle]) -> list:
    model = context.model
    cohort = context.cohort
    scenario = context.scenario
    source_years = [source.year for source in context.sources]
    source_years_text = (
        ", ".join(str(year) for year in source_years[:-1])
        + f" y {source_years[-1]}"
        if source_years
        else "sin fuentes"
    )
    observation_count = cohort.total * len(source_years)
    story: list = []

    # 1 — Portada
    story.extend(
        [
            Spacer(1, 25 * mm),
            Paragraph("PARTICIPA-GEO", styles["title"]),
            Paragraph(
                "Abstención municipal en Jalisco: método, validación y uso responsable "
                "de escenarios 2027",
                styles["subtitle"],
            ),
            Spacer(1, 8 * mm),
            Paragraph(
                "Reporte metodológico y preventivo · Versión 1.0 · "
                f"{context.generated_at.astimezone(UTC).strftime('%d/%m/%Y %H:%M UTC')}",
                styles["body"],
            ),
            Spacer(1, 5 * mm),
            _table(
                [
                    ["Campo", "Valor"],
                    ["Equipo", context.team_slug],
                    ["Eje", context.eje],
                    ["Modelo publicado", f"{model.family} · {model.model_run_id}"],
                    ["Corte territorial", context.reference_date],
                    ["Universo", f"{cohort.total} municipios de Jalisco"],
                    ["Documento", "12 páginas · A4 · resultados derivados de artefactos y base de datos"],
                ],
                widths=[36 * mm, 134 * mm],
            ),
            Spacer(1, 8 * mm),
            _warning(
                "<b>Advertencia de lectura.</b> Este documento no implica efecto causal: "
                "describe asociaciones y predicciones condicionales, no efectos causales. "
                "No contiene datos personales ni permite inferir comportamiento individual. "
                "La referencia cartográfica es 2025-12-15 y no prueba igualdad histórica de "
                "límites."
            ),
            Spacer(1, 8 * mm),
            Paragraph(
                "Fuente primaria: Conteos Censales de Participación Ciudadana (CCPC) del INE, "
                f"{source_years_text}. Los {len(source_years)} archivos oficiales de Jalisco, "
                "sus checksums y el diccionario se incluyen en el paquete técnico de "
                "reproducción.",
                styles["small"],
            ),
        ]
    )
    story.append(PageBreak())

    # 2 — Resumen ejecutivo
    story.extend(
        [
            Paragraph("1. Resumen ejecutivo", styles["h1"]),
            Paragraph(
                f"El modelo seleccionado es <b>{model.family}</b>. En la validación temporal "
                f"{model.validation_year} obtuvo un error absoluto medio (MAE) de "
                f"<b>{_pp(model.mae_2021)}</b>, frente a {_pp(model.m1_mae_2021)} del "
                "candidato sociodemográfico M1; M1 perdió la selección. En la prueba "
                f"posterior a la congelación ({model.test_year}), el MAE de M0 fue "
                f"{_pp(model.mae_2024)} y el de M1 {_pp(model.m1_mae_2024)}.",
                styles["body"],
            ),
            Paragraph(
                f"Para 2027 hay <b>{cohort.total}</b> municipios en el universo. "
                f"<b>{cohort.eligible}</b> tienen información suficiente para una predicción "
                f"condicional y <b>{cohort.insufficient}</b> quedan como información "
                f"insuficiente. De los {cohort.eligible} elegibles, <b>{cohort.unstable}</b> "
                "tienen una categoría de riesgo inestable porque la banda de error cruza un "
                "umbral; por eso el semáforo se muestra con esa advertencia y no como certeza.",
                styles["body"],
            ),
            Spacer(1, 3 * mm),
            Table(
                [
                    [
                        _metric_box(str(cohort.eligible), f"elegibles de {cohort.total}"),
                        _metric_box(str(cohort.insufficient), "información insuficiente"),
                        _metric_box(str(cohort.unstable), "categoría inestable"),
                        _metric_box(_pp(model.band_pp), "banda histórica de referencia"),
                    ]
                ],
                colWidths=[42 * mm] * 4,
                hAlign="LEFT",
            ),
            Spacer(1, 3 * mm),
            Paragraph("Hallazgos que deben guiar la decisión", styles["h2"]),
            Paragraph(
                "• La señal municipal es útil para priorizar revisión y conversación pública, "
                "no para asignar recursos por persona ni para prometer resultados.",
                styles["body"],
            ),
            Paragraph(
                f"• La calidad de datos es el primer filtro: {cohort.insufficient} municipios "
                f"no reciben predicción y {cohort.unstable} de los {cohort.eligible} elegibles "
                "tienen categoría inestable.",
                styles["body"],
            ),
            Paragraph(
                "• Los escenarios A/B son aritmética acotada sobre la predicción publicada. "
                "No son ensayos, no estiman personas y no sustituyen una evaluación de impacto.",
                styles["body"],
            ),
            Paragraph(
                "• El reporte y la presentación se generan desde los mismos artefactos y la "
                "misma base de datos que la interfaz; no hay cifras escritas a mano.",
                styles["body"],
            ),
        ]
    )
    story.append(PageBreak())

    # 3 — Problema y alcance
    story.extend(
        [
            Paragraph("2. Problema, preguntas y alcance", styles["h1"]),
            Paragraph(
                "La abstención electoral es un fenómeno municipal y cambiante. Una lectura "
                "agregada permite identificar territorios donde la participación observada "
                "es baja y donde la información disponible es frágil, sin atribuir la "
                "conducta a características individuales.",
                styles["body"],
            ),
            Paragraph("Preguntas que el sistema responde", styles["h2"]),
            Paragraph(
                "1. ¿Cómo ha evolucionado la participación y la abstención en cada municipio "
                "de Jalisco entre 2009 y 2024?",
                styles["body"],
            ),
            Paragraph(
                "2. ¿Qué abstención estimada y qué banda de error histórico de referencia "
                "puede publicarse para 2027, y en qué municipios la evidencia no alcanza?",
                styles["body"],
            ),
            Paragraph(
                "3. ¿Cómo cambia la comparación si se supone una reducción acotada de la "
                "abstención en municipios elegibles, manteniendo explícitos los supuestos?",
                styles["body"],
            ),
            Paragraph("Lo que el sistema no hace", styles["h2"]),
            Paragraph(
                "No estima intención de voto, no perfila personas, no segmenta por sexo, "
                "edad o sección para persuadir, no asigna presupuesto y no afirma que una "
                "intervención cause un cambio. Tampoco usa datos administrativos ni "
                "identificadores personales.",
                styles["body"],
            ),
            Paragraph(
                "El alcance es un piloto municipal para Jalisco, de uso local, sin "
                "autenticación. La unidad de análisis es el municipio de la referencia "
                "INE 2025; las observaciones históricas conservan su propio año y su "
                "estado de correspondencia.",
                styles["body"],
            ),
            _warning(
                "Regla de interpretación: toda cifra municipal es una estimación agregada "
                "con incertidumbre. La ausencia de una predicción es un resultado de calidad, "
                "no un cero."
            ),
        ]
    )
    story.append(PageBreak())

    # 4 — Fuentes y universo
    source_rows: list[list[Any]] = [["Año", "Archivo / URL", "SHA-256 (prefijo)", "LN"]]
    for source in context.sources:
        source_rows.append(
            [
                source.year,
                f"{source.member.split('/')[-1]}<br/><font size=6>{source.source_url}</font>",
                source.sha256[:16] + "…",
                f"{source.ln:,}" if source.ln else "—",
            ]
        )
    story.extend(
        [
            Paragraph("3. Fuentes, universo y granularidad", styles["h1"]),
            Paragraph(
                f"Se usan los {len(source_years)} CCPC federales de Jalisco "
                f"({source_years_text}). La agregación produce "
                f"<b>{observation_count} observaciones municipales</b> "
                f"({cohort.total} municipios × {len(source_years)} años) y conserva los "
                "conteos LN, SV, NV y NS antes de recalcular tasas. Los agregados estatales "
                "suman conteos; nunca promedian tasas municipales.",
                styles["body"],
            ),
            _table(
                source_rows,
                widths=[13 * mm, 87 * mm, 38 * mm, 32 * mm],
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                "Los archivos fuente son públicos y se incorporan al paquete técnico en su "
                "granularidad original (sección y sexo/edad), sin listas nominales. Esa "
                "excepción documental no se expone en la API: las consultas y exportaciones "
                "analíticas sólo contienen agregados municipales. Está prohibida cualquier "
                "inferencia individual a partir de celdas pequeñas.",
                styles["body"],
            ),
            Paragraph(
                f"Huella del agregado usado por el modelo: "
                f"{context.data_aggregate_sha256}. Las divergencias entre años "
                "(distritos de marco 2021 y 2023, casillas especiales excluidas) se "
                "documentan y no se corrigen silenciosamente.",
                styles["small"],
            ),
            Spacer(1, 2 * mm),
            _warning(
                "Licencias y atribución: los datos son del INE. El paquete conserva URL, "
                "miembro, fecha de corte y checksum de cada archivo. Antes de redistribuir "
                "los originales, el usuario debe confirmar las condiciones aplicables; "
                "si no lo permite, se entregan checksums e instrucciones en lugar de los CSV."
            ),
        ]
    )
    story.append(PageBreak())

    # 5 — Calidad y exclusiones
    cohort_rows: list[list[Any]] = [["Año", "Universo", "Elegibles", "Excluidos", "Motivo principal"]]
    for year in sorted(cohort.eligible_by_year):
        cohort_rows.append(
            [
                year,
                cohort.total,
                cohort.eligible_by_year[year],
                cohort.excluded_by_year.get(year, 0),
                "high_unknown_share",
            ]
        )
    story.extend(
        [
            Paragraph("4. Calidad de datos y exclusiones", styles["h1"]),
            Paragraph(
                "La decisión de calidad es explícita y reproducible. Un municipio se excluye "
                "de la predicción cuando la proporción de no especificados (NS/LN) supera el "
                "umbral fijado; la exclusión se conserva en la tabla de calidad y se muestra "
                "como «información insuficiente», nunca como cero.",
                styles["body"],
            ),
            _table(
                cohort_rows,
                widths=[18 * mm, 30 * mm, 32 * mm, 32 * mm, 58 * mm],
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                f"En 2027, {cohort.eligible} municipios son elegibles y {cohort.insufficient} "
                "no lo son. La cobertura de lista nominal de los elegibles es "
                f"{cohort.eligible_ln:,} de {cohort.total_ln:,} personas en el universo, "
                "lo que debe leerse como cobertura de datos, no como representatividad "
                "de la población.",
                styles["body"],
            ),
            Paragraph("Reglas de calidad", styles["h2"]),
            Paragraph(
                "• Los conteos faltantes o inconsistentes se documentan; no se imputan "
                "ceros ni se inventan tasas.",
                styles["body"],
            ),
            Paragraph(
                "• Los valores nulos de participación o abstención permanecen nulos en "
                "CSV/XLSX, GeoJSON y PDF.",
                styles["body"],
            ),
            Paragraph(
                "• Cada año conserva su versión de dataset y su checksum. La fecha de "
                "generación es metadato variable, no una cifra del modelo.",
                styles["body"],
            ),
        ]
    )
    story.append(PageBreak())

    # 6 — Referencia territorial
    story.extend(
        [
            Paragraph("5. Referencia territorial y correspondencias", styles["h1"]),
            Paragraph(
                "La referencia es la cartografía INE con corte <b>2025-12-15</b>, "
                f"EPSG:4326, con {cohort.total} polígonos municipales. La importación convierte "
                "desde EPSG:32613 con `to_crs` y valida las geometrías; nunca rotula una "
                "geometría UTM como lon/lat.",
                styles["body"],
            ),
            Paragraph(
                "La identidad de catálogo (`identity_status=verified_catalogue`) exige "
                f"coincidencia de código INE, entidad y nombre normalizado en los "
                f"{len(source_years)} CSV y el catálogo de referencia. No prueba igualdad de límites históricos: el "
                "estado de huella es `footprint_status=not_verified` y se muestra en la "
                "interfaz, los documentos y las exportaciones.",
                styles["body"],
            ),
            Paragraph("Consecuencias para mapas y series", styles["h2"]),
            Paragraph(
                "• Los mapas históricos son una representación sobre la referencia 2025; "
                "no muestran los límites contemporáneos de cada elección.",
                styles["body"],
            ),
            Paragraph(
                "• No se redistribuyen conteos mediante intersección de secciones de años "
                "distintos ni se infiere equivalencia INE–INEGI.",
                styles["body"],
            ),
            Paragraph(
                "• Cualquier identidad ambigua o cambio administrativo documentado se marca "
                "no comparable y no recibe pronóstico hasta resolverse.",
                styles["body"],
            ),
            Paragraph(
                f"El GeoJSON de escenario reutiliza exactamente los {cohort.total} polígonos "
                "de esta referencia, sin simplificar, inventar ni re-proyectar. Las "
                "exportaciones A/B contienen los valores persistidos y conservan `null` "
                "cuando la información es insuficiente.",
                styles["body"],
            ),
            _warning(
                "Advertencia 2025: la referencia cartográfica es posterior a las elecciones "
                "históricas. Se usa para identidad administrativa y para los escenarios 2027, "
                "no para afirmar superficie constante."
            ),
        ]
    )
    story.append(PageBreak())

    # 7 — Método
    story.extend(
        [
            Paragraph("6. Método y selección del modelo", styles["h1"]),
            Paragraph(
                "<b>M0 (seleccionado)</b> es una referencia interpretable: usa la abstención "
                "del mismo municipio y mismo tipo de elección en t−6 (2021) para estimar "
                "2027. No utiliza variables sociodemográficas en producción. Su virtud es la "
                "trazabilidad: la estimación se explica por la observación histórica del "
                "propio municipio.",
                styles["body"],
            ),
            Paragraph(
                "<b>M1 (no seleccionado)</b> es un candidato con variables sociodemográficas "
                "(composición joven, mayor, rural y tipo de elección) ajustado con 2015/2018. "
                "Perdió la selección porque su MAE de validación 2021 fue peor "
                f"({_pp(model.m1_mae_2021)} frente a {_pp(model.mae_2021)}).",
                styles["body"],
            ),
            Paragraph("Protocolo", styles["h2"]),
            Paragraph(
                f"• Validación temporal en {model.validation_year} para elegir la familia; "
                f"prueba en {model.test_year} sólo después de congelarla.",
                styles["body"],
            ),
            Paragraph(
                "• No se usa el año de prueba para cambiar variables, alpha ni umbrales.",
                styles["body"],
            ),
            Paragraph(
                f"• Alpha fijo en 1.0. Orden de variables documentado: "
                f"{', '.join(model.feature_order) if model.feature_order else 'no aplica en M0'}.",
                styles["body"],
            ),
            Paragraph(
                "• El modelo se serializa como JSON y parquet, nunca como pickle; las "
                "predicciones publicadas no se recalculan al consultar.",
                styles["body"],
            ),
            _table(
                [
                    ["Elemento", "Valor"],
                    ["Familia seleccionada", model.family],
                    ["Ejecución", str(model.model_run_id)],
                    ["Años de validación / prueba", f"{model.validation_year} / {model.test_year}"],
                    ["Variables M0", "same_type_abstention_pct (t−6)"],
                    ["Reproducibilidad", f"Python {context.versions.get('python', '3.12')} · scikit-learn {context.versions.get('scikit_learn', '—')}"],
                ],
                widths=[45 * mm, 125 * mm],
            ),
        ]
    )
    story.append(PageBreak())

    # 8 — Validación e incertidumbre
    story.extend(
        [
            Paragraph("7. Validación temporal e incertidumbre", styles["h1"]),
            Paragraph(
                "La comparación se hace con el mismo universo elegible de cada año. El MAE "
                "se expresa en puntos porcentuales de abstención; un valor menor es mejor. "
                "M0 gana en validación y también en la prueba posterior, sin haber sido "
                "ajustado con el año de prueba.",
                styles["body"],
            ),
            _table(
                [
                    ["Familia", f"MAE {model.validation_year} (n={model.n_validation})", f"MAE {model.test_year} (n={model.n_test})", "Decisión"],
                    ["M0", _pp(model.mae_2021), _pp(model.mae_2024), "Seleccionada"],
                    ["M1", _pp(model.m1_mae_2021), _pp(model.m1_mae_2024), "Descartada"],
                ],
                widths=[24 * mm, 50 * mm, 50 * mm, 46 * mm],
            ),
            Spacer(1, 3 * mm),
            Paragraph("Banda de error histórico de referencia", styles["h2"]),
            Paragraph(
                f"La banda publicada es la amplitud P90 del error absoluto de M0 en "
                f"{model.validation_year}: <b>{_pp(model.band_pp)}</b>, calculada sobre "
                f"{model.band_n} errores. Se usa como referencia histórica; no promete 90 % "
                "de cobertura futura ni es un intervalo de confianza.",
                styles["body"],
            ),
            Paragraph(
                "La banda se traslada condicionalmente al escenario B y se recorta a 0–100. "
                "No cuantifica el efecto de una intervención ni agrega evidencia. Cuando la "
                "banda cruza un umbral de riesgo, la categoría se marca inestable.",
                styles["body"],
            ),
            Paragraph(
                f"El año {model.test_year} se evaluó una sola vez después de congelar la "
                "familia. La diferencia entre validación y prueba no se usa para reoptimizar; "
                "se documenta como evidencia de estabilidad limitada.",
                styles["body"],
            ),
            _warning(
                "No leer la banda como intervalo causal ni como garantía de cobertura. "
                "La incertidumbre es parte del resultado y se conserva en todos los formatos."
            ),
        ]
    )
    story.append(PageBreak())

    # 9 — Predicción 2027 y semáforo
    risk = cohort.risk_counts
    story.extend(
        [
            Paragraph("8. Predicción 2027 y semáforo analítico", styles["h1"]),
            Paragraph(
                f"Se publican {cohort.total} filas de predicción para 2027. "
                f"{cohort.eligible} tienen estimación y {cohort.insufficient} permanecen "
                "insuficientes. La estimación municipal mediana es "
                f"{_pct(cohort.baseline_median)}; el rango de las estimaciones elegibles va "
                f"de {_pct(cohort.baseline_min)} a {_pct(cohort.baseline_max)}. Estos valores "
                "son descriptivos del universo publicado, no una meta.",
                styles["body"],
            ),
            _table(
                [
                    ["Categoría", "Corte", "Municipios", "Lectura"],
                    ["Bajo", "< 40 %", risk.get("low", 0), "Menor abstención estimada"],
                    ["Medio", "40–<50 %", risk.get("medium", 0), "Seguimiento preventivo"],
                    ["Alto", "≥ 50 %", risk.get("high", 0), "Prioridad de revisión"],
                    ["Insuficiente", "sin estimación", risk.get("insufficient", 0), "Mejorar dato antes de decidir"],
                ],
                widths=[38 * mm, 34 * mm, 32 * mm, 66 * mm],
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                f"De los {cohort.eligible} elegibles, <b>{cohort.unstable}</b> tienen la "
                "categoría inestable. El semáforo no es una clasificación oficial del INE: "
                "es una regla analítica versionada que combina la estimación con la banda "
                "histórica. Se muestra con icono y texto, no sólo con color.",
                styles["body"],
            ),
            Paragraph(
                "La priorización no estima personas ni recursos. Un municipio con categoría "
                "alta e inestable requiere revisión de datos y conversación institucional "
                "antes que una acción comunicacional.",
                styles["body"],
            ),
            _warning(
                "No convertir la categoría en una etiqueta de personas ni en un pronóstico "
                "de conducta individual. La abstención es un agregado municipal."
            ),
        ]
    )
    story.append(PageBreak())

    # 10 — Escenarios
    if scenario is not None:
        scenario_table = _table(
            [
                ["Campo", "Valor"],
                ["Escenario", str(scenario.scenario_id)],
                ["Año objetivo", scenario.target_year],
                ["Municipios seleccionados", scenario.selected_count],
                ["Reducción solicitada / efectiva", f"{scenario.requested_reduction_pp:.1f} pp / {scenario.effective_reduction_pp:.1f} pp"],
                ["Supuesto", f"{scenario.assumption_code} v{scenario.assumption_version}"],
                ["Reglas", scenario.rules_version],
                ["Media A / B en seleccionados", f"{_pct(scenario.baseline_mean)} / {_pct(scenario.hypothetical_mean)}"],
                ["Riesgo A (bajo/medio/alto/insuf.)", "/".join(str(scenario.risk_a_counts.get(k, 0)) for k in ("low", "medium", "high", "insufficient"))],
                ["Riesgo B (bajo/medio/alto/insuf.)", "/".join(str(scenario.risk_b_counts.get(k, 0)) for k in ("low", "medium", "high", "insufficient"))],
            ],
            widths=[58 * mm, 112 * mm],
        )
    else:
        scenario_table = Paragraph(
            "No se incluyó un escenario persistido en esta ejecución. La fórmula y los "
            "supuestos se documentan igualmente; para generar uno, la interfaz exige un "
            "modelo publicado, municipios elegibles y un supuesto del catálogo.",
            styles["body"],
        )
    story.extend(
        [
            Paragraph("9. Escenarios hipotéticos A/B", styles["h1"]),
            Paragraph(
                "A es la abstención estimada 2027 publicada. Para cada municipio seleccionado "
                "y elegible, <b>B = max(0, A − reducción)</b>; los no seleccionados conservan "
                "B = A y los insuficientes permanecen nulos. La reducción efectiva es A − B.",
                styles["body"],
            ),
            scenario_table,
            Spacer(1, 3 * mm),
            Paragraph(
                "El escenario es una comparación aritmética, no un ensayo. No estima cuántas "
                "personas votarían, no cuantifica el efecto de una intervención y no permite "
                "afirmar causalidad. El texto del supuesto proviene de una plantilla "
                "controlada y versionada; no se acepta texto libre del usuario.",
                styles["body"],
            ),
            *(
                [Paragraph(f"Supuesto persistido: {scenario.rationale_text}", styles["small"])]
                if scenario is not None
                else []
            ),
            _warning(
                "Etiqueta obligatoria en interfaz, CSV, GeoJSON y PDF: «rango de error "
                "histórico de referencia trasladado condicionalmente; no es un intervalo "
                "causal»."
            ),
        ]
    )
    story.append(PageBreak())

    # 11 — Recomendaciones
    story.extend(
        [
            Paragraph("10. Recomendaciones y priorización preventiva", styles["h1"]),
            Paragraph(
                "Las recomendaciones son reglas fijas y legibles, no una optimización de "
                "presupuesto ni una segmentación persuasiva. Se derivan de la categoría de "
                "riesgo, la estabilidad de la banda, la elegibilidad y la calidad del dato.",
                styles["body"],
            ),
            _table(
                [
                    ["Señal", "Acción preventiva", "Límite"],
                    ["Dato insuficiente o no especificado alto", "Mejorar captura y revisar la fuente antes de decidir", "No imputar ceros"],
                    ["Riesgo alto", "Considerar revisión institucional y información cívica", "No es una obligación ni una asignación"],
                    ["Categoría inestable", "Monitorear y repetir la lectura con la banda visible", "No presentar la categoría como certeza"],
                    ["Brecha de cobertura", "Advertir equidad y cobertura; no comparar municipios sin denominador", "No inferir personas"],
                ],
                widths=[45 * mm, 82 * mm, 43 * mm],
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                "La priorización es una lista de conversaciones y revisiones, no un ranking "
                "de mérito. Ningún municipio recibe una recomendación por características "
                "individuales; no se usan perfiles partidistas ni segmentación por edad, "
                "sexo o sección.",
                styles["body"],
            ),
            Paragraph(
                "El panel ejecutivo y la interfaz muestran la misma versión de reglas y los "
                "mismos valores. Las exportaciones conservan el identificador del escenario, "
                "los hashes de entrada y modelo, y la etiqueta de no causalidad.",
                styles["body"],
            ),
        ]
    )
    story.append(PageBreak())

    # 12 — Limitaciones y reproducibilidad
    limitation_items = "".join(
        f"<br/>• {limitation}" for limitation in context.limitations
    )
    story.extend(
        [
            Paragraph("11. Limitaciones, uso responsable y reproducibilidad", styles["h1"]),
            Paragraph("Limitaciones", styles["h2"]),
            Paragraph(limitation_items.lstrip("<br/>"), styles["small"]),
            Spacer(1, 2 * mm),
            Paragraph("Reproducibilidad y entrega", styles["h2"]),
            Paragraph(
                f"El paquete técnico incorpora los {len(source_years)} CSV oficiales de "
                "Jalisco y el ZIP cartográfico original únicamente cuando el usuario confirma "
                "la licencia de redistribución; en el modo `--skip-sources` incluye sólo URL y "
                "checksums. En ambos casos añade diccionarios, agregados municipales, "
                "artefactos del modelo y métricas, código, documentación, reportes/mapas y un "
                "manifiesto con checksums. No incluye `.git`, `node_modules`, cachés, `.env`, "
                "cartas firmadas, contactos ni datos personales.",
                styles["body"],
            ),
            Paragraph(
                "Los checksums permiten verificar el paquete sin depender de `/tmp/opencode`. "
                "La instalación limpia puede requerir internet para dependencias e imágenes; "
                "no se promete instalación sin red ni se incluyen imágenes Docker. La fecha "
                "de generación es un metadato variable, no se exige un ZIP binariamente "
                "idéntico.",
                styles["body"],
            ),
            Paragraph(
                "Las firmas, la carta de cesión, la revisión de licencias y el envío final "
                "son comprobaciones humanas. El usuario integra las cartas en un espacio "
                "privado y añade el ZIP técnico; no se sirven por la API ni se automatiza "
                "su envío.",
                styles["body"],
            ),
            _warning(
                "Uso responsable: no usar los agregados para inferir conducta individual, "
                "no presentar la categoría como clasificación oficial y no atribuir "
                "causalidad a una intervención. Conserve fuente, corte, modelo y supuestos "
                "en toda copia."
            ),
            Spacer(1, 2 * mm),
            Paragraph(
                f"Modelo {model.family} · ejecución {model.model_run_id} · corte "
                f"{context.reference_date} · documento generado "
                f"{context.generated_at.astimezone(UTC).isoformat()}.",
                styles["small"],
            ),
        ]
    )
    return story


def generate_executive(context: DeliveryContext) -> bytes:
    """Generate the 9-slide executive deck (accepted ≤10), A4 landscape."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = _document(
        buffer,
        title="Presentación ejecutiva PARTICIPA-GEO",
        pagesize=landscape(A4),
        landscape_mode=True,
    )
    doc.build(
        _executive_story(context, styles),
        onFirstPage=_page_decorator("Presentación ejecutiva · PARTICIPA-GEO", landscape_mode=True),
        onLaterPages=_page_decorator("Presentación ejecutiva · PARTICIPA-GEO", landscape_mode=True),
    )
    return buffer.getvalue()


def _slide(title: str, subtitle: str, body: list, styles) -> list:
    return [
        Paragraph(title, styles["slide_title"]),
        Paragraph(subtitle, styles["subtitle"]),
        *body,
        PageBreak(),
    ]


def _executive_story(context: DeliveryContext, styles) -> list:
    model = context.model
    cohort = context.cohort
    scenario = context.scenario
    source_years = [source.year for source in context.sources]
    source_years_text = (
        ", ".join(str(year) for year in source_years[:-1])
        + f" y {source_years[-1]}"
        if source_years
        else "sin fuentes"
    )
    observation_count = cohort.total * len(source_years)
    story: list = []

    story.extend(
        _slide(
            "PARTICIPA-GEO",
            "Abstención municipal en Jalisco: evidencia para decidir con incertidumbre visible",
            [
                Spacer(1, 8 * mm),
                Table(
                    [
                        [
                            _metric_box(str(cohort.eligible), "municipios elegibles", width=58 * mm),
                            _metric_box(str(cohort.insufficient), "sin predicción", width=58 * mm),
                            _metric_box(_pp(model.mae_2021), "MAE validación 2021", width=58 * mm),
                            _metric_box(_pp(model.band_pp), "banda histórica", width=58 * mm),
                        ]
                    ],
                    colWidths=[58 * mm] * 4,
                    hAlign="LEFT",
                ),
                Spacer(1, 8 * mm),
                Paragraph(
                    f"Modelo {model.family} · corte {context.reference_date} · "
                    f"{cohort.total} municipios · uso local, agregados, sin datos personales.",
                    styles["slide_body"],
                ),
                Paragraph(
                    "<b>No es un pronóstico electoral oficial ni una evaluación causal.</b>",
                    styles["slide_body"],
                ),
            ],
            styles,
        )
    )

    story.extend(
        _slide(
            "1. El problema",
            "La abstención no es uniforme y la información municipal es desigual",
            [
                Paragraph("• La decisión pública necesita una señal municipal comparable.", styles["slide_body"]),
                Paragraph("• No todos los municipios tienen datos suficientemente completos.", styles["slide_body"]),
                Paragraph("• Una cifra sin banda e incertidumbre invita a sobreinterpretar.", styles["slide_body"]),
                Paragraph("• El sistema prioriza revisión y conversación, no asignación automática.", styles["slide_body"]),
                Spacer(1, 4 * mm),
                _warning(
                    "Pregunta guía: ¿dónde conviene mirar primero y dónde hace falta mejorar "
                    "el dato antes de decidir?"
                ),
            ],
            styles,
        )
    )

    story.extend(
        _slide(
            "2. Fuentes y universo",
            "Seis CCPC federales del INE, agregados municipales de Jalisco",
            [
                Paragraph(
                    f"• {source_years_text}: <b>{cohort.total}</b> municipios y "
                    f"<b>{observation_count}</b> observaciones municipales.",
                    styles["slide_body"],
                ),
                Paragraph("• Conteos LN, SV, NV y NS; tasas recalculadas desde los conteos.", styles["slide_body"]),
                Paragraph(
                    f"• Referencia cartográfica INE 2025-12-15, {cohort.total} polígonos "
                    "EPSG:4326.",
                    styles["slide_body"],
                ),
                Paragraph("• Checksums y diccionarios incluidos en el paquete técnico.", styles["slide_body"]),
                _warning(
                    "Límite: la referencia 2025 no prueba igualdad histórica de límites. "
                    "Los CCPC excluyen casillas especiales y residentes en el extranjero."
                ),
            ],
            styles,
        )
    )

    story.extend(
        _slide(
            "3. Método: M0 seleccionado, M1 descartado",
            "La validación temporal decide antes de mirar la prueba",
            [
                Paragraph(
                    "<b>M0:</b> abstención del mismo municipio y tipo de elección en t−6 "
                    "(2021). Interpretable y trazable.",
                    styles["slide_body"],
                ),
                Paragraph(
                    "<b>M1:</b> candidato sociodemográfico ajustado con 2015/2018. "
                    "No se selecciona.",
                    styles["slide_body"],
                ),
                Paragraph(
                    f"Selección en {model.validation_year}: M0 {_pp(model.mae_2021)} vs "
                    f"M1 {_pp(model.m1_mae_2021)}.",
                    styles["slide_body"],
                ),
                Paragraph(
                    f"Prueba posterior en {model.test_year}: M0 {_pp(model.mae_2024)} vs "
                    f"M1 {_pp(model.m1_mae_2024)}.",
                    styles["slide_body"],
                ),
                _warning("M0 no usa variables sociodemográficas en producción. Alpha fijo en 1.0; sin reoptimizar con 2024."),
            ],
            styles,
        )
    )

    story.extend(
        _slide(
            "4. Evidencia",
            "Error absoluto medio en puntos porcentuales de abstención",
            [
                _table(
                    [
                        ["Familia", f"Validación {model.validation_year}", f"Prueba {model.test_year}", "Decisión"],
                        ["M0", _pp(model.mae_2021), _pp(model.mae_2024), "Seleccionada"],
                        ["M1", _pp(model.m1_mae_2021), _pp(model.m1_mae_2024), "Descartada"],
                    ],
                    widths=[45 * mm, 65 * mm, 65 * mm, 65 * mm],
                ),
                Spacer(1, 8 * mm),
                Paragraph(
                    f"Banda de error histórico de referencia: <b>{_pp(model.band_pp)}</b> "
                    f"(P90 de {model.band_n} errores de validación). No es un intervalo de "
                    "confianza ni promete cobertura futura.",
                    styles["slide_body"],
                ),
            ],
            styles,
        )
    )

    risk = cohort.risk_counts
    story.extend(
        _slide(
            "5. Señal 2027",
            "Predicción condicional con calidad y estabilidad visibles",
            [
                Table(
                    [
                        [
                            _metric_box(str(cohort.eligible), "elegibles", width=48 * mm),
                            _metric_box(str(cohort.insufficient), "insuficientes", width=48 * mm),
                            _metric_box(str(cohort.unstable), "categoría inestable", width=48 * mm),
                        ]
                    ],
                    colWidths=[48 * mm] * 3,
                    hAlign="LEFT",
                ),
                Spacer(1, 5 * mm),
                _table(
                    [
                        ["Bajo", "Medio", "Alto", "Insuficiente"],
                        [risk.get("low", 0), risk.get("medium", 0), risk.get("high", 0), risk.get("insufficient", 0)],
                    ],
                    widths=[45 * mm] * 4,
                ),
                Paragraph(
                    f"De {cohort.eligible} elegibles, {cohort.unstable} tienen banda que cruza "
                    "un umbral. El semáforo es analítico, no clasificación oficial.",
                    styles["slide_body"],
                ),
            ],
            styles,
        )
    )

    if scenario is not None:
        scenario_body = [
            Paragraph(
                f"Escenario persistido {scenario.scenario_id}: {scenario.selected_count} "
                f"municipios seleccionados, reducción solicitada "
                f"{scenario.requested_reduction_pp:.1f} pp (efectiva "
                f"{scenario.effective_reduction_pp:.1f} pp).",
                styles["slide_body"],
            ),
            Paragraph(
                f"Media A en seleccionados: {_pct(scenario.baseline_mean)}; "
                f"media B: {_pct(scenario.hypothetical_mean)}.",
                styles["slide_body"],
            ),
            Paragraph(
                f"Riesgo B: bajo {scenario.risk_b_counts.get('low', 0)}, medio "
                f"{scenario.risk_b_counts.get('medium', 0)}, alto "
                f"{scenario.risk_b_counts.get('high', 0)}, insuficiente "
                f"{scenario.risk_b_counts.get('insufficient', 0)}.",
                styles["slide_body"],
            ),
        ]
    else:
        scenario_body = [
            Paragraph(
                "No se incluyó un escenario persistido en esta ejecución. La fórmula es "
                "B = max(0, A − reducción) en municipios elegibles seleccionados.",
                styles["slide_body"],
            )
        ]
    story.extend(
        _slide(
            "6. Escenarios A/B",
            "Comparación hipotética, con supuestos explícitos",
            [
                *scenario_body,
                Spacer(1, 4 * mm),
                _warning(
                    "B no es un efecto causal, no estima personas y no cuantifica una "
                    "intervención. La banda se traslada condicionalmente; no es intervalo causal."
                ),
            ],
            styles,
        )
    )

    story.extend(
        _slide(
            "7. Propuesta",
            "Priorizar revisión, calidad de datos y conversación institucional",
            [
                Paragraph("1. Mejorar el dato donde la predicción es insuficiente.", styles["slide_body"]),
                Paragraph("2. Revisar institucionalmente los municipios de riesgo alto, con la banda visible.", styles["slide_body"]),
                Paragraph("3. Monitorear categorías inestables antes de comunicar una etiqueta.", styles["slide_body"]),
                Paragraph("4. Advertir brechas de cobertura y evitar comparaciones sin denominador.", styles["slide_body"]),
                Paragraph("5. No asignar presupuesto ni personas con esta señal.", styles["slide_body"]),
            ],
            styles,
        )
    )

    story.extend(
        _slide(
            "8. Límites y uso responsable",
            "Lo que la evidencia permite y lo que no",
            [
                Paragraph("• No implica efecto causal ni sustituye una evaluación de impacto.", styles["slide_body"]),
                Paragraph("• No contiene datos personales ni permite inferencia individual.", styles["slide_body"]),
                Paragraph("• Referencia 2025: no promete límites históricos iguales.", styles["slide_body"]),
                Paragraph("• Banda histórica, no intervalo de confianza ni garantía de cobertura.", styles["slide_body"]),
                Paragraph("• Firmas, cesión, licencias y envío final son revisiones humanas.", styles["slide_body"]),
                Spacer(1, 3 * mm),
                _warning(
                    "Conserve fuente, corte, modelo y supuestos en toda copia. "
                    "El paquete técnico y el reporte metodológico contienen el detalle."
                ),
            ],
            styles,
        )
    )
    # The final slide has a trailing PageBreak; the PDF remains 9 pages because
    # ReportLab does not emit an empty page after the last break.
    return story


def generate_scenario_pdf(
    scenario: ScenarioDTO,
    meta: DatasetMeta,
    *,
    context: DeliveryContext | None = None,
) -> bytes:
    """A compact PDF for one persisted scenario (summary + full annex)."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = _document(buffer, title="Escenario hipotético PARTICIPA-GEO")
    rows: list[list[Any]] = [
        ["Municipio", "A", "B", "Reducción efectiva", "Riesgo A", "Riesgo B", "Seleccionado"]
    ]
    effective_reduction = max(
        (row.effective_reduction_pp for row in scenario.results if row.selected),
        default=0.0,
    )
    for result in sorted(scenario.results, key=lambda item: item.municipality_code):
        rows.append(
            [
                f"{result.municipality_code} · {result.municipality_name}",
                _pct(result.baseline_abstention_pct),
                _pct(result.hypothetical_abstention_pct),
                f"{result.effective_reduction_pp:.1f} pp"
                if result.baseline_abstention_pct is not None
                else "—",
                result.risk_a,
                result.risk_b,
                "Sí" if result.selected else "No",
            ]
        )
    story = [
        Paragraph("Escenario hipotético 2027 · comparación A/B", styles["h1"]),
        Paragraph(
            f"Escenario {scenario.scenario_id} · modelo {scenario.model_run_id} · "
            f"corte {meta.reference_date} · supuesto {scenario.assumption_code} "
            f"v{scenario.assumption_version}.",
            styles["body"],
        ),
        _warning(
            "Escenario hipotético — no implica efecto causal. "
            f"{scenario.error_band_label}. No estima personas ni cuantifica una intervención."
        ),
        Spacer(1, 3 * mm),
        _table(
            [
                ["Campo", "Valor"],
                ["Reducción solicitada / efectiva", f"{scenario.requested_reduction_pp:.1f} pp / {effective_reduction:.1f} pp"],
                ["Municipios seleccionados", len(scenario.selected_territory_ids)],
                ["Resultados persistidos", len(scenario.results)],
                ["Hash de entrada", scenario.input_sha256],
                ["Hash del modelo", scenario.model_sha256],
                ["Reglas", scenario.rules_version],
            ],
            widths=[58 * mm, 112 * mm],
        ),
        Spacer(1, 4 * mm),
        Paragraph(f"Anexo: {len(scenario.results)} resultados municipales", styles["h2"]),
        LongTable(
            [
                [
                    Paragraph(str(cell), styles["table_header" if index == 0 else "table_cell"])
                    for cell in row
                ]
                for index, row in enumerate(rows)
            ],
            colWidths=[48 * mm, 17 * mm, 17 * mm, 24 * mm, 18 * mm, 18 * mm, 22 * mm],
            repeatRows=1,
        ),
    ]
    doc.build(
        story,
        onFirstPage=_page_decorator("Escenario hipotético · PARTICIPA-GEO"),
        onLaterPages=_page_decorator("Escenario hipotético · PARTICIPA-GEO"),
    )
    return buffer.getvalue()


__all__ = [
    "generate_executive",
    "generate_methodology",
    "generate_scenario_pdf",
]
