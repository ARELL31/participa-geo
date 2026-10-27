"""GeoServer read-only hardening (internal REST, admin credentials from env).

GeoServer admin credentials are used only over the internal network to configure
the service. Passwords are never logged. The WFS service is pinned to ``BASIC``
(no WFS-T/Transaction), foreign/demo workspaces are removed, and the read-only
behaviour is verified by attempting a WFS ``Transaction`` (which must fail).

The low-level ``_http`` helper is shared with ``bootstrap.py``.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

#: Demo/foreign workspaces shipped by the GeoServer image (removed when present).
_DEMO_WORKSPACES = {
    "ne",
    "it.geosolutions",
    "topp",
    "tiger",
    "sde",
    "sf",
    "spearfish",
    "nurc",
}

WFS_SERVICE_LEVEL = "BASIC"


def auth_header(user: str, password: str) -> dict[str, str]:
    """Build the ``Authorization`` header without logging the secret."""
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _http(
    method: str,
    url: str,
    *,
    auth: dict[str, str],
    body: str | bytes | None = None,
    content_type: str | None = "application/json",
    timeout: float = 30.0,
) -> tuple[int, bytes]:
    """Perform an HTTP request, returning ``(status, body)`` (no exceptions)."""
    data = body.encode("utf-8") if isinstance(body, str) else body
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in auth.items():
        request.add_header(key, value)
    if data is not None and content_type:
        request.add_header("Content-Type", content_type)
    request.add_header("Accept", "*/*")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise ConnectionError(f"GeoServer unreachable at {url}: {exc.reason}") from exc


def json_body(body: bytes) -> Any:
    return json.loads(body.decode("utf-8")) if body else None


def set_wfs_read_only(base_url: str, auth: dict[str, str]) -> dict[str, Any]:
    """Pin WFS to ``BASIC`` service level (disables WFS-T/Transaction)."""
    payload = json.dumps({"wfs": {"serviceLevel": WFS_SERVICE_LEVEL}})
    status, body = _http(
        "PUT", f"{base_url}/rest/services/wfs/settings", auth=auth, body=payload
    )
    if status not in (200, 201):
        raise RuntimeError(f"failed to set WFS service level ({status}): {body!r}")
    return {"service_level": WFS_SERVICE_LEVEL}


def get_wfs_settings(base_url: str, auth: dict[str, str]) -> dict[str, Any] | None:
    status, body = _http("GET", f"{base_url}/rest/services/wfs/settings", auth=auth)
    if status != 200:
        return None
    parsed = json_body(body)
    return parsed.get("wfs") if isinstance(parsed, dict) else parsed


def remove_foreign_workspaces(
    base_url: str, auth: dict[str, str], *, keep: set[str]
) -> list[str]:
    """Delete any shipped demo/foreign workspace other than ``keep``."""
    removed: list[str] = []
    status, body = _http("GET", f"{base_url}/rest/workspaces", auth=auth)
    if status != 200:
        return removed
    parsed = json_body(body) or {}
    workspaces = parsed.get("workspaces", {}).get("workspace", [])
    if isinstance(workspaces, dict):
        workspaces = [workspaces]
    for ws in workspaces:
        name = ws.get("name")
        if name and name not in keep:
            _http("DELETE", f"{base_url}/rest/workspaces/{name}?recurse=true", auth=auth)
            removed.append(name)
    return removed


def verify_transaction_rejected(base_url: str, auth: dict[str, str]) -> bool:
    """Return True when a WFS ``Transaction`` is rejected by the server."""
    url = (
        f"{base_url}/wfs?service=WFS&version=2.0.0&request=Transaction"
    )
    status, _ = _http(
        "POST",
        url,
        auth=auth,
        body=(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<wfs:Transaction service="WFS" version="2.0.0" '
            'xmlns:wfs="http://www.opengis.net/wfs/2.0">'
            "</wfs:Transaction>"
        ),
        content_type="application/xml",
    )
    return status != 200


__all__ = [
    "WFS_SERVICE_LEVEL",
    "auth_header",
    "get_wfs_settings",
    "remove_foreign_workspaces",
    "set_wfs_read_only",
    "verify_transaction_rejected",
]
