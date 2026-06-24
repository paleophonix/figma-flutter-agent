"""HTML helpers for HTTP preview reverse proxy."""

from __future__ import annotations

import re
from urllib.parse import quote

_PREVIEW_BASE_TAG_RE = re.compile(r"<base\s", re.IGNORECASE)
_HEAD_OPEN_RE = re.compile(r"<head([^>]*)>", re.IGNORECASE)

PREVIEW_AUTH_COOKIE = "figma_cp_preview"

_FLUTTER_ROOT_ASSET_NAMES = (
    "flutter_bootstrap.js",
    "flutter.js",
    "main.dart.js",
    "manifest.json",
    "favicon.png",
    "version.json",
)


def preview_cookie_value(*, job_id: str, mode: str, token: str) -> str:
    """Serialize preview auth for an HttpOnly cookie."""
    return f"{job_id}|{mode}|{token}"


def parse_preview_cookie(raw: str) -> tuple[str, str, str] | None:
    """Parse ``job_id|mode|token`` preview cookie payload."""
    parts = raw.split("|", 2)
    if len(parts) != 3:
        return None
    job_id, mode, token = parts
    if not job_id or mode not in {"fixed", "adaptive"} or not token:
        return None
    return job_id, mode, token


def rewrite_preview_root_paths(content: bytes, *, job_id: str) -> bytes:
    """Rewrite root-absolute Flutter web asset URLs for the preview proxy path."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    prefix = f"/preview/{quote(job_id, safe='')}"
    for name in _FLUTTER_ROOT_ASSET_NAMES:
        text = text.replace(f'"/{name}"', f'"{prefix}/{name}"')
        text = text.replace(f"'/{name}'", f"'{prefix}/{name}'")
    text = text.replace('"/assets/', f'"{prefix}/assets/')
    text = text.replace("'/assets/", f"'{prefix}/assets/")
    text = text.replace('"/canvaskit/', f'"{prefix}/canvaskit/')
    text = text.replace("'/canvaskit/", f"'{prefix}/canvaskit/")
    return text.encode("utf-8")


def inject_preview_base_href(content: bytes, *, job_id: str) -> bytes:
    """Insert a base tag so relative Flutter web assets resolve under the proxy."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    if "<head" not in text.lower():
        return content
    if _PREVIEW_BASE_TAG_RE.search(text):
        return content
    base = f'<base href="/preview/{quote(job_id, safe="")}/">'
    updated, count = _HEAD_OPEN_RE.subn(rf"<head\1>\n    {base}", text, count=1)
    if count == 0:
        return content
    return updated.encode("utf-8")
