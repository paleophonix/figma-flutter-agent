"""Figma URL parsing utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from figma_flutter_agent.errors import FigmaUrlError

if TYPE_CHECKING:
    from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry

_FILE_KEY_PATTERN = re.compile(r"figma\.com/(?:file|design)/([a-zA-Z0-9]+)")


class FigmaUrlKind(StrEnum):
    """Whether a Figma input refers to a whole file or one frame."""

    FILE = "file"
    FRAME = "frame"


@dataclass(frozen=True)
class ParsedFigmaUrl:
    """Parsed Figma file and node identifiers."""

    file_key: str
    node_id: str


@dataclass(frozen=True)
class ParsedFigmaInput:
    """Parsed Figma URL or raw file key with detected scope."""

    kind: FigmaUrlKind
    file_key: str
    node_id: str | None = None
    source: str = ""

    @property
    def is_file(self) -> bool:
        """Return True when the input targets a whole Figma file."""
        return self.kind == FigmaUrlKind.FILE

    @property
    def is_frame(self) -> bool:
        """Return True when the input targets one frame node."""
        return self.kind == FigmaUrlKind.FRAME


def _normalize_node_id(raw_node_id: str) -> str:
    node_id = raw_node_id.replace("-", ":")
    if ":" not in node_id:
        raise FigmaUrlError(f"Invalid node id format: {raw_node_id}")
    return node_id


def parse_figma_input(raw: str) -> ParsedFigmaInput:
    """Parse a Figma URL or file key and detect file vs frame scope.

    Args:
        raw: Figma design/file URL, or a bare file key string.

    Returns:
        ``ParsedFigmaInput`` with ``kind`` ``file`` or ``frame``.

    Raises:
        FigmaUrlError: When the value is empty or malformed.
    """
    trimmed = raw.strip()
    if not trimmed:
        raise FigmaUrlError("Figma URL or file key is empty")

    if "figma.com" in trimmed:
        file_key = parse_figma_file_key(trimmed)
        query = parse_qs(urlparse(trimmed).query)
        raw_node_id = query.get("node-id", [None])[0]
        if raw_node_id:
            node_id = _normalize_node_id(raw_node_id)
            return ParsedFigmaInput(
                kind=FigmaUrlKind.FRAME,
                file_key=file_key,
                node_id=node_id,
                source=trimmed,
            )
        return ParsedFigmaInput(
            kind=FigmaUrlKind.FILE,
            file_key=file_key,
            node_id=None,
            source=trimmed,
        )

    return ParsedFigmaInput(
        kind=FigmaUrlKind.FILE,
        file_key=trimmed,
        node_id=None,
        source=trimmed,
    )


def describe_figma_input(parsed: ParsedFigmaInput) -> str:
    """Human-readable summary of a parsed Figma input."""
    if parsed.is_frame and parsed.node_id is not None:
        return f"single frame {parsed.node_id} in file {parsed.file_key}"
    return f"full Figma file {parsed.file_key}"


def _active_screen_entry(
    manifest: BatchManifest,
    active_screen: str | None,
) -> ScreenEntry | None:
    if not manifest.screens:
        return None
    if active_screen:
        for screen in manifest.screens:
            if screen.feature == active_screen:
                return screen
    return manifest.screens[0]


def _unique_candidates(*values: str | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value:
            continue
        trimmed = value.strip()
        if not trimmed or trimmed in seen:
            continue
        seen.add(trimmed)
        ordered.append(trimmed)
    return ordered


def resolve_default_figma_input(
    *,
    prefer_kind: FigmaUrlKind | None = None,
    manifest: BatchManifest | None = None,
    active_screen: str | None = None,
    figma_default_url: str = "",
    figma_smoke_file_key: str = "",
    figma_smoke_node_id: str = "",
) -> str:
    """Pick the best default Figma URL/key for interactive prompts.

    Precedence (first parseable match for ``prefer_kind``):

    1. ``screens.yaml`` — ``figma_file_url``, active screen URL, or ``file_key``
    2. ``FIGMA_DEFAULT_URL`` env
    3. ``FIGMA_SMOKE_FILE_KEY`` / ``FIGMA_SMOKE_NODE_ID`` env

    Args:
        prefer_kind: When set, only return defaults of that scope.
        manifest: Optional batch manifest for project memory.
        active_screen: Feature slug to prefer when resolving frame URLs.
        figma_default_url: ``FIGMA_DEFAULT_URL`` from settings.
        figma_smoke_file_key: ``FIGMA_SMOKE_FILE_KEY`` from settings.
        figma_smoke_node_id: ``FIGMA_SMOKE_NODE_ID`` from settings.

    Returns:
        Default input string, or empty when nothing matches.
    """
    smoke_key = figma_smoke_file_key.strip()
    smoke_node = figma_smoke_node_id.strip().replace("-", ":")
    smoke_frame_url = build_figma_url(smoke_key, smoke_node) if smoke_key and smoke_node else None

    file_candidates: list[str | None] = []
    frame_candidates: list[str | None] = []
    any_candidates: list[str | None] = []

    if manifest is not None:
        screen = _active_screen_entry(manifest, active_screen)
        file_candidates.extend([manifest.figma_file_url, manifest.file_key])
        if screen is not None:
            frame_candidates.append(screen.figma_url)
            if manifest.file_key and screen.node_id:
                frame_candidates.append(build_figma_url(manifest.file_key, screen.node_id))
        any_candidates.extend(
            [
                manifest.figma_file_url,
                screen.figma_url if screen is not None else None,
                build_figma_url(manifest.file_key, screen.node_id)
                if screen is not None and manifest.file_key and screen.node_id
                else None,
                manifest.file_key,
            ]
        )

    file_candidates.extend([figma_default_url, smoke_key or None])
    frame_candidates.extend([figma_default_url, smoke_frame_url])
    any_candidates.extend([figma_default_url, smoke_frame_url, smoke_key or None])

    if prefer_kind == FigmaUrlKind.FILE:
        candidates = _unique_candidates(*file_candidates)
    elif prefer_kind == FigmaUrlKind.FRAME:
        candidates = _unique_candidates(*frame_candidates)
    else:
        candidates = _unique_candidates(*any_candidates)

    for candidate in candidates:
        try:
            parsed = parse_figma_input(candidate)
        except FigmaUrlError:
            continue
        if prefer_kind is None or parsed.kind == prefer_kind:
            return candidate
    return ""


def parse_figma_url(url: str) -> ParsedFigmaUrl:
    """Parse a Figma file URL and extract file key and node id.

    Args:
        url: Figma file or design URL containing a node-id query parameter.

    Returns:
        Parsed file key and normalized node id.

    Raises:
        FigmaUrlError: If the URL or node id is invalid.
    """
    match = _FILE_KEY_PATTERN.search(url)
    if not match:
        raise FigmaUrlError(f"Could not extract file key from URL: {url}")

    query = parse_qs(urlparse(url).query)
    raw_node_id = query.get("node-id", [None])[0]
    if not raw_node_id:
        raise FigmaUrlError("Figma URL must include a node-id query parameter")

    node_id = raw_node_id.replace("-", ":")
    if ":" not in node_id:
        raise FigmaUrlError(f"Invalid node id format: {raw_node_id}")

    return ParsedFigmaUrl(file_key=match.group(1), node_id=node_id)


def parse_figma_file_key(url: str) -> str:
    """Extract the file key from a Figma file or design URL.

    Args:
        url: Figma URL with or without a ``node-id`` query parameter.

    Returns:
        File key string.

    Raises:
        FigmaUrlError: If the URL does not contain a file key.
    """
    match = _FILE_KEY_PATTERN.search(url)
    if not match:
        raise FigmaUrlError(f"Could not extract file key from URL: {url}")
    return match.group(1)


def build_figma_url(file_key: str, node_id: str) -> str:
    """Build a minimal Figma design URL for ``parse_figma_url``.

    Args:
        file_key: Figma file key.
        node_id: Node id with colon separator (``1:3570``).

    Returns:
        Parseable Figma design URL.
    """
    dashed = node_id.replace(":", "-")
    return f"https://www.figma.com/design/{file_key}/batch-screen?node-id={dashed}"


def resolve_smoke_frame(
    *,
    figma_url: str | None,
    file_key: str,
    node_id: str,
) -> tuple[str, str]:
    """Resolve smoke frame ids from ``--figma-url`` or ``FIGMA_SMOKE_*`` env fields.

    Args:
        figma_url: Optional Figma design URL; when set, overrides env smoke vars.
        file_key: ``FIGMA_SMOKE_FILE_KEY`` value from settings.
        node_id: ``FIGMA_SMOKE_NODE_ID`` value from settings.

    Returns:
        Tuple of ``(file_key, node_id)`` with colon-normalized node id.

    Raises:
        FigmaUrlError: When ``figma_url`` is provided but invalid.
    """
    if figma_url and figma_url.strip():
        parsed = parse_figma_url(figma_url.strip())
        return parsed.file_key, parsed.node_id
    return file_key.strip(), node_id.strip()
