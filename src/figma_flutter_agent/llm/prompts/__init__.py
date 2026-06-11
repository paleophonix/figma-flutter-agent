"""LLM system prompts for codegen, analyze repair, and visual refine."""

from __future__ import annotations

from figma_flutter_agent.llm.prompts.cpi import render_cpi_supervisor_prompt
from figma_flutter_agent.llm.prompts.generation import build_system_prompt
from figma_flutter_agent.llm.prompts.models import (
    FIGMA_REFERENCE_INLINE_LABEL,
    FIGMA_REFERENCE_ONLY_LABEL,
    FLUTTER_RENDER_INLINE_LABEL,
    REFERENCE_USER_PREAMBLE,
    USER_LABELS,
    VISUAL_DIFF_INLINE_LABEL,
    VISUAL_REFINE_IMAGE_INTRO,
    VISUAL_REFINE_USER_PREAMBLE,
    CpiSupervisorContext,
    MultimodalUserLabels,
)
from figma_flutter_agent.llm.prompts.principles import (
    SYSTEMIC_BUG_RULES,
    build_systemic_bug_registry_l3,
)
from figma_flutter_agent.llm.prompts.repair import (
    build_repair_system_prompt,
    render_escalated_metacognitive_repair_prompt,
    render_repair_system_prompt,
)
from figma_flutter_agent.llm.prompts.visual import (
    build_visual_refine_system_prompt,
    visual_refine_attached_images,
)

__all__ = [
    "CpiSupervisorContext",
    "FIGMA_REFERENCE_INLINE_LABEL",
    "FIGMA_REFERENCE_ONLY_LABEL",
    "FLUTTER_RENDER_INLINE_LABEL",
    "MultimodalUserLabels",
    "REFERENCE_USER_PREAMBLE",
    "SYSTEMIC_BUG_RULES",
    "USER_LABELS",
    "VISUAL_DIFF_INLINE_LABEL",
    "VISUAL_REFINE_IMAGE_INTRO",
    "VISUAL_REFINE_USER_PREAMBLE",
    "build_repair_system_prompt",
    "build_system_prompt",
    "build_systemic_bug_registry_l3",
    "build_visual_refine_system_prompt",
    "render_cpi_supervisor_prompt",
    "render_escalated_metacognitive_repair_prompt",
    "render_repair_system_prompt",
    "visual_refine_attached_images",
]
