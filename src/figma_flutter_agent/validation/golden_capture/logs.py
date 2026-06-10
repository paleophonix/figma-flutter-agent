"""Process output logging helpers for golden capture."""

from __future__ import annotations

import re
import subprocess

from loguru import logger

_MAX_REASON_LEN = 160
_DART_DIAGNOSTIC_RE = re.compile(r"\.dart:\d+:\d+:\s*Error:")
_SKIP_LINE_PREFIXES = (
    "Resolving dependencies",
    "Downloading packages",
    "Got dependencies",
    "Syncing files",
    'Running "flutter pub get"',
    "Running flutter pub get",
)
_RENDERFLEX_OVERFLOW_RE = re.compile(
    r"A RenderFlex overflowed by ([\d.]+) pixels",
    re.IGNORECASE,
)
_RENDERFLEX_WIDGET_RE = re.compile(
    r"\.dart:(\d+):\d+",
)

_HIGH_SIGNAL_LINE_PATTERNS = (
    re.compile(r"A Stack requires bounded constraints"),
    re.compile(r"RenderFlex overflowed"),
    re.compile(r"Bad state:"),
    re.compile(r"Test failed"),
    re.compile(r"EXCEPTION CAUGHT BY"),
    re.compile(r"Multiple exceptions"),
    _DART_DIAGNOSTIC_RE,
)


def collect_renderflex_overflows(
    stdout: str | None,
    stderr: str | None,
) -> tuple[str, ...]:
    """Return human-readable RenderFlex overflow lines from flutter test output."""
    combined = "\n".join(part for part in (stdout or "", stderr or "") if part)
    if not combined.strip():
        return ()
    messages: list[str] = []
    lines = combined.splitlines()
    for index, line in enumerate(lines):
        match = _RENDERFLEX_OVERFLOW_RE.search(line)
        if match is None:
            continue
        pixels = match.group(1)
        location = ""
        for follow in lines[index : index + 8]:
            loc = _RENDERFLEX_WIDGET_RE.search(follow.replace("\\", "/"))
            if loc is not None and ".dart:" in follow:
                location = f" at {follow.strip()}"
                break
        messages.append(f"RenderFlex overflowed by {pixels}px{location}")
    return tuple(messages)


def _clip_reason(text: str) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= _MAX_REASON_LEN:
        return stripped
    return f"{stripped[: _MAX_REASON_LEN - 3]}..."


def _log_process_output(result: subprocess.CompletedProcess[str], *, level: str = "debug") -> None:
    combined = "\n".join(
        part for part in (result.stdout or "", result.stderr or "") if part.strip()
    ).strip()
    if not combined:
        return
    tail = combined[-4000:]
    if level == "warning":
        logger.warning("Golden capture subprocess output (tail):\n{}", tail)
    else:
        logger.debug("Golden capture subprocess output (tail):\n{}", tail)


def _first_process_line(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "").strip()
    if not text:
        return "flutter test failed"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for stripped in reversed(lines):
        if any(pattern.search(stripped) for pattern in _HIGH_SIGNAL_LINE_PATTERNS):
            normalized = stripped.replace("\\", "/")
            if _DART_DIAGNOSTIC_RE.search(stripped) and (
                "/lib/" in normalized or normalized.startswith("lib/")
            ):
                return _clip_reason(stripped)
            if not _DART_DIAGNOSTIC_RE.search(stripped):
                return _clip_reason(stripped)
    diagnostics: list[str] = []
    for stripped in lines:
        if _DART_DIAGNOSTIC_RE.search(stripped):
            diagnostics.append(stripped)
    for stripped in diagnostics:
        normalized = stripped.replace("\\", "/")
        if "/lib/" in normalized or normalized.startswith("lib/"):
            return _clip_reason(stripped)
    if diagnostics:
        return _clip_reason(diagnostics[0])
    for stripped in reversed(lines):
        if any(stripped.startswith(prefix) for prefix in _SKIP_LINE_PREFIXES):
            continue
        return _clip_reason(stripped)
    return _clip_reason(lines[0] if lines else "flutter test failed")
