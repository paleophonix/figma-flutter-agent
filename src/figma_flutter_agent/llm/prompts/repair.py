"""Analyze-repair prompt builders."""

from __future__ import annotations

from string import Template

from figma_flutter_agent.llm.prompts.actions import _REPAIR_L5, _REPAIR_L5_UNIFIED_DIFF
from figma_flutter_agent.llm.prompts.capabilities import _CPI_L4, _REPAIR_L4
from figma_flutter_agent.llm.prompts.compose import _compose_acdp_prompt
from figma_flutter_agent.llm.prompts.environment import (
    _ESCALATED_REPAIR_L6_EXTRA,
    _REPAIR_L6_TEMPLATE,
)
from figma_flutter_agent.llm.prompts.principles import (
    _CPI_L3,
    _L3_SYSTEMIC_BUG_REGISTRY,
    _REPAIR_L3,
    _REPAIR_L3_IR_PATCHES,
)
from figma_flutter_agent.llm.prompts.shared import _CPI_L1, _CPI_L2, _REPAIR_L1, _REPAIR_L2, _join_sections
from figma_flutter_agent.llm.repair_scope import RepairEnvironmentContext

def render_repair_system_prompt(context: RepairEnvironmentContext) -> str:
    """Render the APR repair system prompt with ``string.Template.safe_substitute``.

    Args:
        context: ``L6:ENVIRONMENT`` fields built by ``repair_scope``.

    Returns:
        Repair system prompt with analyzer errors, numbered source, and history injected.
    """
    l6 = Template(_REPAIR_L6_TEMPLATE).safe_substitute(
        analyzeErrors=context.analyze_errors,
        code=context.code,
        semanticHint=context.semantic_hint,
        failedAttemptsHistory=context.failed_attempts_history,
        unchangedWidgetNames=context.unchanged_widget_names,
        cpiSupervisorDirective=context.cpi_supervisor_directive,
        repairEscalationBlock="(none — standard APR level 1)",
    )
    return _compose_acdp_prompt(
        l1=_REPAIR_L1,
        l2=_REPAIR_L2,
        l3_core=_join_sections(_REPAIR_L3, _L3_SYSTEMIC_BUG_REGISTRY),
        l4=_REPAIR_L4,
        l5_core=_join_sections(_REPAIR_L5, _REPAIR_L5_UNIFIED_DIFF),
        l6=l6,
    )


def build_repair_system_prompt(
    context: RepairEnvironmentContext | None = None,
    *,
    use_screen_ir: bool = False,
) -> str:
    """Build the APR system prompt for ``llm_repair`` / dart-analyze patch mode.

    Theme-agnostic: repair targets are taken from the user JSON payload; L6 holds
    numbered source and analyzer output from ``repair_scope``.

    Args:
        context: Environment substitutions for ``<L6:ENVIRONMENT>``. When omitted,
            uses empty-safe placeholder defaults for tests.

    Returns:
        System prompt string for repair patch structured output.
    """
    if context is None:
        context = RepairEnvironmentContext(
            analyze_errors="(none)",
            code="(empty file)",
            semantic_hint="null",
            failed_attempts_history="(no prior failed patches in this run)",
            unchanged_widget_names="(none)",
        )
    prompt = render_repair_system_prompt(context)
    if use_screen_ir:
        return f"{prompt}\n\n{_REPAIR_L3_IR_PATCHES}"
    return prompt


def render_escalated_metacognitive_repair_prompt(
    context: RepairEnvironmentContext,
    *,
    escalation_level: int,
    tactical_directive: str,
    target_file: str,
    attempt: int,
    max_attempts: int,
) -> str:
    """Replace the APR system prompt with metacognitive supervisor + repair L6 bindings."""
    base_l6 = Template(_REPAIR_L6_TEMPLATE).safe_substitute(
        analyzeErrors=context.analyze_errors,
        code=context.code,
        semanticHint=context.semantic_hint,
        failedAttemptsHistory=context.failed_attempts_history,
        unchangedWidgetNames=context.unchanged_widget_names,
        cpiSupervisorDirective=context.cpi_supervisor_directive,
        repairEscalationBlock="(see Tactical Directive below — LEVEL 2+ metacognitive shift active)",
    )
    extra_l6 = Template(_ESCALATED_REPAIR_L6_EXTRA).safe_substitute(
        escalationLevel=str(escalation_level),
        loopAttempt=f"{attempt}/{max_attempts}",
        targetFile=target_file,
        tacticalDirective=tactical_directive,
    )
    l6 = f"{base_l6}\n{extra_l6}"
    l5_sections = [tactical_directive, _REPAIR_L5, _REPAIR_L5_UNIFIED_DIFF]
    return _compose_acdp_prompt(
        l1=_CPI_L1,
        l2=_CPI_L2,
        l3_core=_join_sections(_CPI_L3, _REPAIR_L3, _L3_SYSTEMIC_BUG_REGISTRY),
        l4=_join_sections(_CPI_L4, _REPAIR_L4),
        l5_core=_join_sections(*l5_sections),
        l6=l6,
    )
