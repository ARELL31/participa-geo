"""Bounded GeoServer gateway client and strict request validation.

The gateway is a read-only allowlist proxy: it accepts only GetCapabilities,
GetMap, GetFeatureInfo and GetFeature against the published layers, validates
bbox/width/height/count, and builds any internal filter from a validated
``scenario_id`` (UUID) or ``year`` (election year) — never from client CQL/SQL.
"""

from __future__ import annotations

import math
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from participa_geo.api.errors import ProblemException, problem
from participa_geo.ingestion.schema import ELECTION_YEARS

WORKSPACE = "participa_geo"
NATIONAL_WORKSPACE = "participa_geo_national"
NATIONAL_LAYERS = frozenset({"states", "municipalities", "districts_2023"})


class AllowedLayer(StrEnum):
    states = "states"
    municipalities = "municipalities"
    districts_2023 = "districts_2023"
    participation_history = "participation_history"
    predictions = "predictions"
    scenario_results = "scenario_results"


PUBLISHED_LAYERS = frozenset(layer.value for layer in AllowedLayer)

WMS_REQUESTS = frozenset({"GetCapabilities", "GetMap", "GetFeatureInfo"})
WFS_REQUESTS = frozenset({"GetCapabilities", "GetFeature"})
WMS_VERSIONS = frozenset({"1.1.1", "1.3.0"})
WFS_VERSIONS = frozenset({"1.0.0", "1.1.0", "2.0.0"})
WMS_CRS = frozenset({"EPSG:4326", "EPSG:3857"})
WMS_FORMATS = frozenset({"image/png", "image/jpeg"})
WMS_INFO_FORMATS = frozenset({"text/plain", "application/json"})
WFS_OUTPUT_FORMATS = frozenset(
    {"application/json", "json", "application/gml+xml; version=3.2", "gml32", "GML3"}
)
MAX_WIDTH = MAX_HEIGHT = 1200
MAX_COUNT = 1000

_WMS_ALLOWED_PARAMS = frozenset(
    {
        "service",
        "version",
        "request",
        "layers",
        "styles",
        "bbox",
        "width",
        "height",
        "srs",
        "crs",
        "format",
        "transparent",
        "bgcolor",
        "exceptions",
        "query_layers",
        "info_format",
        "i",
        "j",
        "feature_count",
        "scenario_id",
        "year",
    }
)
_WFS_ALLOWED_PARAMS = frozenset(
    {
        "service",
        "version",
        "request",
        "typename",
        "typenames",
        "count",
        "startindex",
        "srsname",
        "outputformat",
        "bbox",
        "scenario_id",
        "year",
        "state_code",
        "level",
    }
)


@dataclass(frozen=True)
class Bounds:
    minx: float
    miny: float
    maxx: float
    maxy: float


class GeoServerError(RuntimeError):
    """Raised when the internal GeoServer request fails."""


def _invalid(message: str) -> ProblemException:
    return ProblemException(
        problem(
            status=422,
            code="validation_error",
            title="Validación fallida",
            detail=message,
        )
    )


def _normalize_layer(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise _invalid("capa vacía")
    if ":" in stripped:
        workspace, layer = stripped.split(":", 1)
        if layer not in PUBLISHED_LAYERS or workspace not in {WORKSPACE, NATIONAL_WORKSPACE}:
            raise _invalid(f"capa no publicada: {stripped}")
        if layer not in NATIONAL_LAYERS and workspace == NATIONAL_WORKSPACE:
            raise _invalid(f"capa no publicada: {stripped}")
        return f"{workspace}:{layer}"
    if stripped not in PUBLISHED_LAYERS:
        raise _invalid(f"capa no publicada: {stripped}")
    workspace = NATIONAL_WORKSPACE if stripped in NATIONAL_LAYERS else WORKSPACE
    return f"{workspace}:{stripped}"


def _qualified_layer(layer: AllowedLayer) -> str:
    workspace = NATIONAL_WORKSPACE if layer.value in NATIONAL_LAYERS else WORKSPACE
    return f"{workspace}:{layer.value}"


def _normalize_layers(value: str) -> str:
    return ",".join(_normalize_layer(name) for name in value.split(","))


def _validate_bbox(value: str | None) -> None:
    if value is None:
        raise _invalid("falta bbox")
    parts = value.split(",")
    if len(parts) not in (4, 5):
        raise _invalid("bbox inválido")
    try:
        coords = [float(p) for p in parts[:4]]
    except ValueError:
        raise _invalid("bbox no numérico") from None
    if not all(math.isfinite(c) for c in coords):
        raise _invalid("bbox no finito")
    minx, miny, maxx, maxy = coords
    if minx > maxx or miny > maxy:
        raise _invalid("bbox no ordenado")


def _parse_size(width: str | None, height: str | None) -> tuple[int, int]:
    if width is None or height is None:
        raise _invalid("GetMap/GetFeatureInfo requiere width y height")
    try:
        w, h = int(width), int(height)
    except ValueError:
        raise _invalid("width/height no entero") from None
    if not (1 <= w <= MAX_WIDTH and 1 <= h <= MAX_HEIGHT):
        raise _invalid("width/height fuera de límites")
    return w, h


def _validate_size(width: str | None, height: str | None) -> None:
    _parse_size(width, height)


def _validate_pixel(i: str | None, j: str | None, width: str | None, height: str | None) -> None:
    if i is None or j is None:
        raise _invalid("GetFeatureInfo requiere i y j")
    w, h = _parse_size(width, height)
    try:
        pixel_i, pixel_j = int(i), int(j)
    except ValueError:
        raise _invalid("i/j no entero") from None
    if not (0 <= pixel_i < w and 0 <= pixel_j < h):
        raise _invalid("i/j fuera de los límites del mapa")


def _validate_crs(value: str | None, key: str, allowed: frozenset) -> None:
    if value is None:
        return
    if value not in allowed:
        raise _invalid(f"{key} no permitido: {value}")


def _build_cql(scenario_id: str | None, year: str | None, layers: str) -> str | None:
    """Build an internal CQL filter from a validated UUID/year (never client CQL)."""
    if scenario_id is None and year is None:
        return None
    if scenario_id is not None:
        if "scenario_results" not in layers:
            raise _invalid("scenario_id sólo aplica a la capa scenario_results")
        try:
            UUID(scenario_id)
        except (ValueError, AttributeError):
            raise _invalid("scenario_id inválido") from None
        return f"scenario_id = '{scenario_id}'"
    if "participation_history" not in layers:
        raise _invalid("year sólo aplica a la capa participation_history")
    try:
        year_int = int(year)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise _invalid("year inválido") from None
    if year_int not in ELECTION_YEARS:
        raise _invalid("year no permitido")
    return f"year = {year_int}"


def validate_wms_request(params: Mapping[str, str]) -> dict[str, str]:
    """Validate and sanitise a WMS request; raises ``ProblemException`` (422)."""
    out: dict[str, str] = {}
    for raw_name in params.keys():
        name = raw_name.lower()
        if name not in _WMS_ALLOWED_PARAMS:
            raise _invalid(f"parámetro no permitido: {raw_name}")
        out[name] = params[raw_name]

    if out.get("service", "WMS").upper() != "WMS":
        raise _invalid("service debe ser WMS")
    out["service"] = "WMS"

    request = out.get("request")
    if request is None:
        raise _invalid("falta request")
    if request not in WMS_REQUESTS:
        raise _invalid(f"request no permitido: {request}")
    out["request"] = request

    version = out.get("version")
    if version is not None and version not in WMS_VERSIONS:
        raise _invalid("version no permitida")
    out["version"] = version or "1.3.0"

    if request in ("GetMap", "GetFeatureInfo"):
        layers = out.get("layers")
        if not layers:
            raise _invalid(f"{request} requiere layers")
        normalized_layers = _normalize_layers(layers)
        out["layers"] = normalized_layers
        _validate_bbox(out.get("bbox"))
        _validate_crs(out.get("srs"), "srs", WMS_CRS)
        _validate_crs(out.get("crs"), "crs", WMS_CRS)
        if "srs" not in out and "crs" not in out:
            out["srs"] = "EPSG:3857"
        if request == "GetMap":
            _validate_size(out.get("width"), out.get("height"))
            fmt = out.get("format", "image/png")
            if fmt not in WMS_FORMATS:
                raise _invalid("format no permitido")
            out["format"] = fmt
        else:
            query_layers = out.get("query_layers")
            if not query_layers:
                raise _invalid("GetFeatureInfo requiere query_layers")
            normalized_query = _normalize_layers(query_layers)
            published = set(normalized_layers.split(","))
            if any(layer not in published for layer in normalized_query.split(",")):
                raise _invalid("query_layers debe referirse a capas incluidas en layers")
            out["query_layers"] = normalized_query
            _validate_pixel(
                out.get("i"),
                out.get("j"),
                out.get("width"),
                out.get("height"),
            )
            info_format = out.get("info_format", "text/plain")
            if info_format not in WMS_INFO_FORMATS:
                raise _invalid("info_format no permitido")
            out["info_format"] = info_format
    elif request == "GetCapabilities" and "layers" in out:
        out["layers"] = _normalize_layers(out["layers"])

    cql = _build_cql(out.pop("scenario_id", None), out.pop("year", None), out.get("layers", ""))
    if cql:
        out["cql_filter"] = cql
    return out


def validate_wfs_request(params: Mapping[str, str]) -> dict[str, str]:
    """Validate and sanitise a WFS request; raises ``ProblemException`` (422)."""
    out: dict[str, str] = {}
    for raw_name in params.keys():
        name = raw_name.lower()
        if name not in _WFS_ALLOWED_PARAMS:
            raise _invalid(f"parámetro no permitido: {raw_name}")
        out[name] = params[raw_name]

    if out.get("service", "WFS").upper() != "WFS":
        raise _invalid("service debe ser WFS")
    out["service"] = "WFS"

    request = out.get("request")
    if request is None:
        raise _invalid("falta request")
    if request not in WFS_REQUESTS:
        raise _invalid(f"request no permitido: {request}")
    out["request"] = request

    version = out.get("version")
    if version is not None and version not in WFS_VERSIONS:
        raise _invalid("version no permitida")
    out["version"] = version or "2.0.0"

    if request == "GetFeature":
        type_names = out.get("typenames", out.get("typename"))
        if not type_names:
            raise _invalid("GetFeature requiere typeNames")
        out["typeNames"] = _normalize_layers(type_names)

        state_code = out.get("state_code")
        if state_code is not None:
            if not state_code.isdigit() or not 1 <= int(state_code) <= 32:
                raise _invalid("state_code debe estar entre 01 y 32")
            out["state_code"] = state_code.zfill(2)
        level = out.get("level")
        if level is not None and level not in {"municipality", "federal_district"}:
            raise _invalid("level debe ser municipality o federal_district")
        if level == "municipality" and "districts_2023" in type_names:
            raise _invalid("level municipality no coincide con districts_2023")
        if level == "federal_district" and "municipalities" in type_names:
            raise _invalid("level federal_district no coincide con municipalities")
        if state_code is None and "bbox" not in out:
            raise _invalid("WFS GetFeature requiere state_code o bbox")

        count = out.get("count")
        if count is not None:
            try:
                count_int = int(count)
            except ValueError:
                raise _invalid("count no entero") from None
            if not (1 <= count_int <= MAX_COUNT):
                raise _invalid("count fuera de límites")
        else:
            count_int = MAX_COUNT
        out["count"] = str(count_int)

        _validate_crs(out.get("srsname"), "srsName", WMS_CRS)
        fmt = out.get("outputformat", "application/json")
        if fmt not in WFS_OUTPUT_FORMATS:
            raise _invalid("outputFormat no permitido")
        out["outputFormat"] = fmt
        if "bbox" in out:
            _validate_bbox(out["bbox"])
    cql = _build_cql(
        out.pop("scenario_id", None),
        out.pop("year", None),
        out.get("typeNames", ""),
    )
    state_filter = f"state_code = '{out['state_code']}'" if out.get("state_code") else None
    if cql and state_filter:
        out["cql_filter"] = f"({cql}) AND ({state_filter})"
    elif cql or state_filter:
        out["cql_filter"] = cql or state_filter
    return out


class GeoServerClient:
    """Read-only client to the internal GeoServer (fixed host from settings)."""

    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def forward(self, service: str, params: Mapping[str, str]) -> tuple[int, str, bytes]:
        """Forward a sanitized request to ``/wms`` or ``/wfs``; return (status, type, body)."""
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}/{service}?{query}"
        request = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.headers.get_content_type(), response.read()
        except urllib.error.HTTPError as exc:
            ctype = exc.headers.get_content_type() if exc.headers else "application/xml"
            return exc.code, ctype, exc.read()
        except urllib.error.URLError as exc:
            raise GeoServerError(f"GeoServer unreachable: {exc.reason}") from exc

    def get_map(
        self,
        layer: AllowedLayer,
        scenario_id: UUID | None,
        year: int | None,
        bbox: Bounds,
        width: int,
        height: int,
        *,
        srs: str = "EPSG:3857",
        format: str = "image/png",
        styles: str = "",
    ) -> bytes:
        """Fetch one WMS GetMap (internal filters built from UUID/year).

        ``styles`` is a server-side style name only; it is never taken from a
        client request, so this cannot be used to load an arbitrary SLD.
        """
        params: dict[str, str] = {
            "service": "WMS",
            "version": "1.1.1",
            "request": "GetMap",
            "layers": _qualified_layer(layer),
            "styles": styles,
            "bbox": f"{bbox.minx},{bbox.miny},{bbox.maxx},{bbox.maxy}",
            "width": str(width),
            "height": str(height),
            "srs": srs,
            "format": format,
        }
        cql = _build_cql(
            str(scenario_id) if scenario_id else None,
            str(year) if year else None,
            layer.value,
        )
        if cql:
            params["cql_filter"] = cql
        status, _, body = self.forward("wms", params)
        if status != 200:
            raise GeoServerError(f"GetMap failed with status {status}")
        return body

    def get_features(
        self,
        layer: AllowedLayer,
        scenario_id: UUID | None,
        year: int | None,
        *,
        count: int = MAX_COUNT,
        bbox: Bounds | None = None,
        state_code: str | None = None,
    ) -> bytes:
        """Fetch one WFS GetFeature (internal filters built from UUID/year)."""
        params: dict[str, str] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": _qualified_layer(layer),
            "count": str(count),
            "srsName": "EPSG:4326",
            "outputFormat": "application/json",
        }
        cql = _build_cql(
            str(scenario_id) if scenario_id else None,
            str(year) if year else None,
            layer.value,
        )
        if cql:
            params["cql_filter"] = cql
        if bbox is not None:
            params["bbox"] = f"{bbox.minx},{bbox.miny},{bbox.maxx},{bbox.maxy}"
        if state_code is not None:
            if layer.value not in NATIONAL_LAYERS or not (
                state_code.isdigit() and len(state_code) == 2
            ):
                raise ValueError("state_code inválido para capa nacional")
            params["cql_filter"] = f"state_code = '{state_code}'"
        status, _, body = self.forward("wfs", params)
        if status != 200:
            raise GeoServerError(f"GetFeature failed with status {status}")
        return body


__all__ = [
    "AllowedLayer",
    "Bounds",
    "GeoServerClient",
    "GeoServerError",
    "MAX_COUNT",
    "PUBLISHED_LAYERS",
    "WMS_INFO_FORMATS",
    "WORKSPACE",
    "validate_wfs_request",
    "validate_wms_request",
]
