"""Extract Figma frame URLs from GitLab issue descriptions."""

from __future__ import annotations

import re

from figma_flutter_agent.errors import FigmaUrlError
from figma_flutter_agent.figma.url import parse_figma_url

_FIGMA_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']*figma\.com/(?:file|design)/[a-zA-Z0-9]+[^\s<>\"']*",
    re.IGNORECASE,
)


def extract_figma_frame_urls(text: str) -> list[str]:
    """Return Figma URLs with ``node-id`` found in ``text``."""
    found: list[str] = []
    for match in _FIGMA_URL_PATTERN.finditer(text or ""):
        candidate = match.group(0).rstrip(").,]")
        try:
            parse_figma_url(candidate)
        except FigmaUrlError:
            continue
        found.append(candidate)
    return found


def extract_first_figma_frame_url(text: str) -> str:
    """Return the first valid Figma frame URL from ``text``.

    Args:
        text: GitLab issue description or note body.

    Returns:
        Canonical Figma frame URL string.

    Raises:
        FigmaUrlError: When no frame URL is present or multiple frames are found.
    """
    urls = extract_figma_frame_urls(text)
    if not urls:
        raise FigmaUrlError("GitLab issue description must include a Figma frame URL with node-id")
    if len(urls) > 1:
        raise FigmaUrlError("GitLab issue description must include exactly one Figma frame URL")
    return urls[0]
