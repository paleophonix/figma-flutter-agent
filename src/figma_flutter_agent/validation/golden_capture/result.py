"""Shared result type for golden capture runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from figma_flutter_agent.validation.golden_capture.capture_host import (
        GoldenCaptureHostSession,
    )
    from figma_flutter_agent.validation.golden_capture.warm_runtime import (
        GoldenCaptureTimings,
    )


@dataclass(frozen=True)
class GoldenCaptureResult:
    """Outcome of an offline golden capture attempt."""

    png: bytes | None = None
    reason: str | None = None
    figma_key_rects: dict[str, Any] | None = None
    host_session: GoldenCaptureHostSession | None = None
    renderflex_overflows: tuple[str, ...] = ()
    timings: GoldenCaptureTimings | None = None

    @property
    def ok(self) -> bool:
        """True when golden PNG bytes were captured."""
        return self.png is not None and len(self.png) > 0
