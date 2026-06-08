"""Font diagnostic data models."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.fonts.local import FontMatchKind


@dataclass(frozen=True)
class FontAuditRow:
    """One font diagnostic line for doctor / wizard output."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class DesignFontFaceStatus:
    """One font face required by the active screen dump."""

    family: str
    weight: str
    style: str | None
    expected_basename: str
    found_basename: str | None
    match: FontMatchKind
