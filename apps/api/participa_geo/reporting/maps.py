"""Static A/B scenario maps composed from the GeoServer scenario layer.

Both requests target the same ``scenario_results`` layer and the same EPSG:3857
extent at 1200×900. A uses the ``risk_a`` style (filed on ``risk_a``) and B the
published default ``risk`` style (``risk_b``). The composed PNG/PDF carries one
shared legend, the cut date, model, scenario and the explicit non-causal warning.

Any GeoServer error, XML ServiceException (even with HTTP 200), non-image body or
undecodable PNG raises :class:`MapRenderError`; a placeholder is never returned.
"""

from __future__ import annotations

import io
import time
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer

from participa_geo.api.gis_client import (
    AllowedLayer,
    Bounds,
    GeoServerClient,
    GeoServerError,
)
from participa_geo.api.schemas.scenarios import ScenarioDTO

#: Jalisco extent in WGS84; transformed to EPSG:3857 for GetMap.
JALISCO_BOUNDS_WGS84 = (-105.7, 18.9, -101.5, 22.75)
MAP_WIDTH = 1200
MAP_HEIGHT = 900
GIS_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 30.0

RISK_COLORS = {
    "low": "#2E7D32",
    "medium": "#F9A825",
    "high": "#C62828",
    "insufficient": "#9E9E9E",
}
RISK_LABELS = {
    "low": "Bajo (< 40 %)",
    "medium": "Medio (40–<50 %)",
    "high": "Alto (≥ 50 %)",
    "insufficient": "Sin estimación",
}

BACKGROUND = "#F7F6F5"
SURFACE = "#FFFFFF"
PRIMARY = "#6F1739"
TEXT = "#252525"
MUTED = "#666666"
BORDER = "#E6E0E2"


class MapRenderError(RuntimeError):
    """Raised when a real A/B map cannot be obtained from GeoServer."""


def _bounds_3857() -> Bounds:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    minx, miny = transformer.transform(JALISCO_BOUNDS_WGS84[0], JALISCO_BOUNDS_WGS84[1])
    maxx, maxy = transformer.transform(JALISCO_BOUNDS_WGS84[2], JALISCO_BOUNDS_WGS84[3])
    return Bounds(minx=minx, miny=miny, maxx=maxx, maxy=maxy)


def _font_paths() -> tuple[Path | None, Path | None]:
    candidates = [
        Path(__file__).resolve().parents[4] / "docs" / "hackathon" / "fonts",
        Path.cwd() / "docs" / "hackathon" / "fonts",
    ]
    for directory in candidates:
        regular = directory / "Inter-Regular.ttf"
        bold = directory / "Inter-SemiBold.ttf"
        if regular.is_file():
            return regular, bold if bold.is_file() else regular
    return None, None


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    regular, semi = _font_paths()
    path = semi if bold else regular
    if path is not None:
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            pass
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _fetch(client: GeoServerClient, scenario: ScenarioDTO, *, styles: str) -> bytes:
    try:
        return client.get_map(
            AllowedLayer.scenario_results,
            scenario.scenario_id,
            None,
            _bounds_3857(),
            MAP_WIDTH,
            MAP_HEIGHT,
            srs="EPSG:3857",
            format="image/png",
            styles=styles,
        )
    except GeoServerError as exc:
        raise MapRenderError(f"GeoServer no devolvió el mapa: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - any transport failure is an explicit GIS failure
        raise MapRenderError(f"fallo al solicitar el mapa a GeoServer: {exc}") from exc


def _open_png(payload: bytes, label: str) -> Image.Image:
    if not payload or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise MapRenderError(
            f"{label}: GeoServer devolvió un cuerpo que no es PNG "
            "(posible ServiceExceptionReport)"
        )
    try:
        image = Image.open(io.BytesIO(payload))
        image.load()
    except Exception as exc:  # noqa: BLE001 - invalid image is a hard failure
        raise MapRenderError(f"{label}: PNG inválido ({exc})") from exc
    if image.width != MAP_WIDTH or image.height != MAP_HEIGHT:
        raise MapRenderError(
            f"{label}: se esperaban {MAP_WIDTH}×{MAP_HEIGHT} px, "
            f"GeoServer devolvió {image.width}×{image.height}"
        )
    return image.convert("RGB")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill: str,
    max_width: int,
    *,
    line_height: int,
) -> int:
    x, y = xy
    for line in _wrap(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def compose_png(
    scenario: ScenarioDTO,
    image_a: Image.Image,
    image_b: Image.Image,
    *,
    generated_at: datetime | None = None,
) -> bytes:
    """Compose the two maps with one legend, metadata and the warning."""
    generated_at = generated_at or datetime.now(UTC)
    canvas = Image.new("RGB", (1600, 1160), BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    title_font = _load_font(34, bold=True)
    subtitle_font = _load_font(19)
    panel_font = _load_font(22, bold=True)
    body_font = _load_font(18)
    small_font = _load_font(16)

    draw.rectangle((0, 0, 1600, 96), fill=PRIMARY)
    draw.text(
        (40, 24),
        "PARTICIPA-GEO · Comparación cartográfica A/B 2027",
        font=title_font,
        fill="#FFFFFF",
    )
    draw.text(
        (40, 66),
        "Escenario hipotético — no implica efecto causal · agregados municipales",
        font=subtitle_font,
        fill="#F4E6EB",
    )

    panel_w, panel_h = 750, 562
    positions = [(35, 130), (815, 130)]
    for label, image, position in zip(
        ("A · Línea base 2027", "B · Escenario hipotético 2027"),
        (image_a, image_b),
        positions,
        strict=True,
    ):
        x, y = position
        draw.rectangle(
            (x - 1, y - 1, x + panel_w + 1, y + panel_h + 1),
            outline=BORDER,
            width=2,
            fill=SURFACE,
        )
        draw.text((x + 14, y + 8), label, font=panel_font, fill=PRIMARY)
        resized = image.resize((panel_w - 20, panel_h - 58), Image.Resampling.LANCZOS)
        canvas.paste(resized, (x + 10, y + 48))

    # Shared legend: identical classes and colors for A and B.
    legend_y = 714
    draw.rectangle((35, legend_y, 1565, legend_y + 92), fill=SURFACE, outline=BORDER)
    draw.text(
        (55, legend_y + 12),
        "Leyenda compartida A/B — mismos cortes",
        font=panel_font,
        fill=TEXT,
    )
    x = 55
    for key in ("low", "medium", "high", "insufficient"):
        draw.rectangle((x, legend_y + 52, x + 26, legend_y + 74), fill=RISK_COLORS[key])
        draw.text((x + 36, legend_y + 50), RISK_LABELS[key], font=body_font, fill=TEXT)
        x += 360

    metadata_y = 828
    draw.text((40, metadata_y), "Fuente y metadatos", font=panel_font, fill=PRIMARY)
    lines = [
        "Fuente cartográfica: INE 2025-12-15 (EPSG:4326) publicada por GeoServer como "
        "participa_geo:scenario_results; mapas A/B en EPSG:3857, 1200×900.",
        f"Escenario: {scenario.scenario_id} · modelo: {scenario.model_run_id} · "
        f"corte: 2025-12-15 · reglas: {scenario.rules_version}",
        f"Supuesto: {scenario.assumption_code} v{scenario.assumption_version} · "
        f"reducción solicitada: {scenario.requested_reduction_pp:.1f} pp · "
        f"fecha de generación: {generated_at.astimezone(UTC).isoformat()}",
        "B = max(0, A − reducción) sólo en municipios seleccionados y elegibles. "
        "La banda es un rango de error histórico de referencia trasladado; "
        "no es un intervalo causal.",
        "Uso responsable: no estimar personas, no inferir comportamiento individual y no "
        "atribuir causalidad a una intervención.",
    ]
    y = metadata_y + 34
    for line in lines:
        y = _draw_wrapped(
            draw,
            (40, y),
            line,
            small_font,
            TEXT if line is lines[0] else MUTED,
            1520,
            line_height=22,
        )
        y += 4
    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def compose_pdf(
    scenario: ScenarioDTO,
    image_a: Image.Image,
    image_b: Image.Image,
    *,
    generated_at: datetime | None = None,
) -> bytes:
    """Embed the composed PNG in a one-page A4 landscape PDF with metadata."""
    png = compose_png(
        scenario, image_a, image_b, generated_at=generated_at
    )
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas

    buffer = io.BytesIO()
    page = landscape(A4)
    pdf = pdf_canvas.Canvas(buffer, pagesize=page)
    width, height = page
    pdf.setFillColor("#6F1739")
    pdf.rect(0, height - 42, width, 42, fill=1, stroke=0)
    pdf.setFillColor("#FFFFFF")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(24, height - 27, "PARTICIPA-GEO · Mapa comparativo A/B 2027")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        24,
        20,
        "Escenario hipotético. Fuente: INE 2025-12-15 / GeoServer scenario_results. "
        "No implica efecto causal; agregados municipales.",
    )
    image = ImageReader(io.BytesIO(png))
    available_w = width - 48
    available_h = height - 94
    ratio = min(available_w / png_width(png), available_h / png_height(png))
    draw_w = png_width(png) * ratio
    draw_h = png_height(png) * ratio
    pdf.drawImage(
        image,
        (width - draw_w) / 2,
        34,
        width=draw_w,
        height=draw_h,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def png_width(payload: bytes) -> int:
    with Image.open(io.BytesIO(payload)) as image:
        return image.width


def png_height(payload: bytes) -> int:
    with Image.open(io.BytesIO(payload)) as image:
        return image.height


def fetch_scenario_images(
    scenario: ScenarioDTO,
    *,
    client: GeoServerClient | None = None,
) -> tuple[Image.Image, Image.Image]:
    """Fetch both A and B GetMap images first, then validate both."""
    if client is None:
        from participa_geo.settings import Settings

        client = GeoServerClient(
            Settings().gis_base_url, timeout=GIS_TIMEOUT_SECONDS
        )
    started = time.monotonic()
    payload_a = _fetch(client, scenario, styles="risk_a")
    payload_b = _fetch(client, scenario, styles="")
    if time.monotonic() - started > TOTAL_TIMEOUT_SECONDS:
        raise MapRenderError("la generación de mapas superó el límite de 30 s")
    return _open_png(payload_a, "A"), _open_png(payload_b, "B")


def render_scenario_map(
    scenario: ScenarioDTO,
    kind: str,
    *,
    client: GeoServerClient | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    """Return a PNG or PDF composed from real GeoServer A/B maps."""
    fmt = kind.lower()
    if fmt not in {"png", "pdf"}:
        raise ValueError("kind debe ser 'png' o 'pdf'")
    if client is None:
        from participa_geo.settings import Settings

        client = GeoServerClient(
            Settings().gis_base_url, timeout=GIS_TIMEOUT_SECONDS
        )
    image_a, image_b = fetch_scenario_images(scenario, client=client)
    if fmt == "png":
        return compose_png(scenario, image_a, image_b, generated_at=generated_at)
    return compose_pdf(scenario, image_a, image_b, generated_at=generated_at)


__all__ = [
    "GIS_TIMEOUT_SECONDS",
    "MAP_HEIGHT",
    "MAP_WIDTH",
    "MapRenderError",
    "RISK_COLORS",
    "compose_pdf",
    "compose_png",
    "fetch_scenario_images",
    "render_scenario_map",
]
