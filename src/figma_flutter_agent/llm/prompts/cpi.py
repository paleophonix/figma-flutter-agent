"""CPI supervisor prompt builder."""

from __future__ import annotations

from string import Template

from figma_flutter_agent.llm.prompts.actions import _CPI_L5
from figma_flutter_agent.llm.prompts.capabilities import _CPI_L4
from figma_flutter_agent.llm.prompts.compose import _compose_acdp_prompt
from figma_flutter_agent.llm.prompts.environment import _CPI_L6_TEMPLATE
from figma_flutter_agent.llm.prompts.models import CpiSupervisorContext
from figma_flutter_agent.llm.prompts.principles import _CPI_L3
from figma_flutter_agent.llm.prompts.shared import _CPI_L1, _CPI_L2


def render_cpi_supervisor_prompt(context: CpiSupervisorContext) -> str:
    """Render the CPI loop-supervisor system prompt (optional repair escalation tier).

    Args:
        context: Historical patch and error metrics for stagnation detection.

    Returns:
        System prompt string for CPI supervisor structured output.
    """
    l6 = Template(_CPI_L6_TEMPLATE).safe_substitute(
        lastPatches=context.last_patches,
        recurringErrors=context.recurring_errors,
        figmaNodeIntent=context.figma_node_intent,
    )
    return _compose_acdp_prompt(
        l1=_CPI_L1,
        l2=_CPI_L2,
        l3_core=_CPI_L3,
        l4=_CPI_L4,
        l5_core=_CPI_L5,
        l6=l6,
    )
