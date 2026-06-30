"""Cached dump fetch/parse reused across wizard preflight and offline pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.stages.fetch import FigmaFetchResult
from figma_flutter_agent.stages.parse import FigmaParseResult


@dataclass(frozen=True)
class ScreenDumpPrefetch:
    """One parsed screen dump snapshot reused across wizard preflight and pipeline."""

    dump_path: Path
    fetch_result: FigmaFetchResult
    parse_result: FigmaParseResult

    def matches_dump(self, dump_path: Path) -> bool:
        """Return True when ``dump_path`` resolves to the same file as this prefetch."""
        return self.dump_path.resolve() == dump_path.resolve()
