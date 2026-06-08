"""Models for wizard render previews."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ViewRendersResult:
    """Outcome of a wizard combat-render capture session."""

    render_dir: Path
    figma_reference_ok: bool
    flutter_capture_ok: bool
    diff_ok: bool
    changed_ratio: float | None = None
    warnings: tuple[str, ...] = ()
