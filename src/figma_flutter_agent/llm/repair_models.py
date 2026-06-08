"""LLM repair data models."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.schemas import FlutterGenerationResponse


@dataclass(frozen=True)
class RepairApplyOutcome:
    """Result of merging LLM repair patches into a generation payload."""

    generation: FlutterGenerationResponse
    patches_applied: int = 0
    patches_rejected: int = 0
    ir_patches_applied: int = 0
