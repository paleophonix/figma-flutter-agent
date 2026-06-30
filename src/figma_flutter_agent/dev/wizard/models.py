"""Wizard data models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from figma_flutter_agent.pipeline.dump_prefetch import ScreenDumpPrefetch


@dataclass(frozen=True)
class DoctorCheck:
    """One environment readiness check."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    """Aggregated wizard environment report."""

    checks: tuple[DoctorCheck, ...]

    @property
    def passed(self) -> bool:
        """Return True when every check succeeded."""
        return all(item.ok for item in self.checks)


@dataclass(frozen=True)
class ScreenPreflight:
    """Readiness summary for one manifest screen."""

    feature: str
    dump_exists: bool
    dump_path: Path | None
    wired_feature: str | None
    wired_matches: bool
    exportable_icons: int
    local_icons: int
    missing_asset_exports: int
    dump_prefetch: ScreenDumpPrefetch | None = None

    @property
    def needs_live_sync(self) -> bool:
        """Return True when a live Figma frame fetch is required (no cached dump)."""
        return not self.dump_exists

    @property
    def needs_live_asset_sync(self) -> bool:
        """Return True when SVG/raster assets are missing on disk but a dump exists."""
        return self.dump_exists and self.missing_asset_exports > 0
