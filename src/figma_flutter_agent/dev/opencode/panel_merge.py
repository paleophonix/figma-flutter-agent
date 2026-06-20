"""Fusion panel metadata persistence (M5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from figma_flutter_agent.config.debug_pipeline import DebugPipelineStep
    from figma_flutter_agent.llm.openrouter_fusion import OpenRouterFusionInvocation

_PANEL_DIR = Path(".repair/state")


def persist_fusion_metadata(
    step: DebugPipelineStep,
    invocation: OpenRouterFusionInvocation,
    *,
    state_dir: Path | None = None,
) -> Path | None:
    """Record Fusion outer model and panel slugs for audit."""
    if not invocation.use_fusion:
        return None
    base = state_dir or _PANEL_DIR
    panel_dir = base / step / "panel"
    panel_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "model": invocation.model,
        "judge_model": invocation.judge_model,
        "analysis_models": list(invocation.analysis_models or ()),
    }
    path = panel_dir / "fusion.json"
    path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return path
