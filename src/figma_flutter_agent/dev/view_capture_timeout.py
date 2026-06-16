"""Capture timeout policy for warm-sandbox ``flutter test`` runs."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.tools.ast_sidecar.types import AST_SIDECAR_MAX_SOURCE_BYTES

_VIEW_RENDER_MIN_CAPTURE_TIMEOUT_SEC = 1200.0
_VIEW_RENDER_LARGE_CAPTURE_TIMEOUT_SEC = 1200.0


def capture_settings_for_planned(
    settings: Settings,
    planned: dict[str, str],
) -> Settings:
    """Raise capture timeout for warm-sandbox ``flutter test`` (first compile can exceed 5 min)."""
    layout_bytes = max(
        (
            len(content.encode("utf-8"))
            for path, content in planned.items()
            if path.replace("\\", "/").startswith("lib/generated/")
            and path.endswith("_layout.dart")
        ),
        default=0,
    )
    base = settings.agent.generation.golden_capture_timeout_sec
    extended = max(base, _VIEW_RENDER_MIN_CAPTURE_TIMEOUT_SEC)
    if layout_bytes > AST_SIDECAR_MAX_SOURCE_BYTES:
        extended = max(extended, _VIEW_RENDER_LARGE_CAPTURE_TIMEOUT_SEC)
    if extended <= base:
        return settings
    if layout_bytes > AST_SIDECAR_MAX_SOURCE_BYTES:
        logger.info(
            "Large generated layout ({} KiB); flutter test capture timeout {:.0f}s",
            layout_bytes // 1024,
            extended,
        )
    else:
        logger.info(
            "Warm sandbox first compile; flutter test capture timeout {:.0f}s",
            extended,
        )
    return settings.model_copy(
        update={
            "agent": settings.agent.model_copy(
                update={
                    "generation": settings.agent.generation.model_copy(
                        update={"golden_capture_timeout_sec": extended},
                    ),
                },
            ),
        },
    )
