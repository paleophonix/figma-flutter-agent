"""CPI loop supervisor — metacognitive escalation when analyze repair stagnates."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.llm.payload_format import format_labeled_user_payload
from figma_flutter_agent.llm.payload_slim import dump_clean_tree_for_llm
from figma_flutter_agent.llm.prompts import CpiSupervisorContext
from figma_flutter_agent.llm.repair_scope import (
    dedupe_analyze_errors,
    format_analyze_errors_block,
    format_failed_attempts_history,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def build_cpi_supervisor_context(
    *,
    failed_attempts_history: list[str],
    analyze_errors: list[str],
    clean_tree: CleanDesignTreeNode | None,
) -> CpiSupervisorContext:
    """Build L6 bindings for the CPI supervisor system prompt."""
    unique_errors = dedupe_analyze_errors(analyze_errors)
    figma_intent = dump_clean_tree_for_llm(clean_tree) if clean_tree is not None else "null"
    return CpiSupervisorContext(
        last_patches=format_failed_attempts_history(failed_attempts_history),
        recurring_errors=format_analyze_errors_block(unique_errors),
        figma_node_intent=figma_intent,
    )


def build_cpi_supervisor_user_payload(*, feature_name: str) -> str:
    """Minimal user payload for CPI supervisor structured output."""
    sections: dict[str, Any] = {
        "featureName": feature_name,
        "instruction": (
            "The primary repair agent repeated failed patches without resolving "
            "recurringErrors. Emit analysis and an uppercase tactical patternInterruptDirective."
        ),
    }
    return format_labeled_user_payload(
        mode="cpi_supervisor",
        output_schema="RepairCpiSupervisorResponse JSON (analysis, patternInterruptDirective)",
        sections=sections,
    )
