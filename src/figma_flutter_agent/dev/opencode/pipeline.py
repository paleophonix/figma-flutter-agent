"""Backward-compatible facade for the repair pipeline package."""

from figma_flutter_agent.dev.opencode.pipeline.orchestrator import run_repair_pipeline
from figma_flutter_agent.dev.opencode.pipeline.types import OpenCodeRepairClient, PipelineOutcome

__all__ = ["OpenCodeRepairClient", "PipelineOutcome", "run_repair_pipeline"]
