"""Human approval gates between repair pipeline steps."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol


class StepGate(Protocol):
    """Approve or deny advancing to the next pipeline step."""

    async def approve(self, step: str, *, preview: dict[str, Any] | None = None) -> bool:
        """Return True to run ``step``, False to stop the pipeline."""
        ...


class AutoApproveStepGate:
    """Always continue (headless / tests)."""

    async def approve(self, step: str, *, preview: dict[str, Any] | None = None) -> bool:
        _ = step, preview
        return True


class WizardStepGate:
    """Typer yes/no prompt before each step (wizard debug)."""

    async def approve(self, step: str, *, preview: dict[str, Any] | None = None) -> bool:
        from figma_flutter_agent.wizard.prompts import prompt_confirm

        message = f"Proceed to repair pipeline step '{step}'?"
        if preview:
            hint = preview.get("hint")
            if isinstance(hint, str) and hint:
                message = f"{message} {hint}"
        return await asyncio.to_thread(prompt_confirm, message, default=True)


class WizardRoundGate:
    """Typer yes/no prompt before each outer correction round (wizard debug)."""

    async def approve(self, step: str, *, preview: dict[str, Any] | None = None) -> bool:
        from figma_flutter_agent.wizard.prompts import prompt_confirm

        round_label = step.removeprefix("round_") if step.startswith("round_") else step
        message = f"Proceed to correction round {round_label}?"
        if preview:
            hint = preview.get("hint")
            if isinstance(hint, str) and hint:
                message = f"{message} {hint}"
        return await asyncio.to_thread(prompt_confirm, message, default=True)


def resolve_step_gate(
    *,
    confirm_next_step: bool,
    command: str,
    explicit: StepGate | None = None,
) -> StepGate | None:
    """Return a step gate when interactive confirmation is enabled."""
    if explicit is not None:
        return explicit
    if confirm_next_step and command == "wizard_debug":
        return WizardStepGate()
    return None


def resolve_round_gate(
    *,
    confirm_next_round: bool,
    command: str,
    explicit: StepGate | None = None,
) -> StepGate | None:
    """Return a round gate when interactive outer-loop confirmation is enabled."""
    if explicit is not None:
        return explicit
    if confirm_next_round and command == "wizard_debug":
        return WizardRoundGate()
    return None
