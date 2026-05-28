"""Stateful repair system-prompt escalation (attempt 1 → 4)."""

from __future__ import annotations

from typing import Final

from loguru import logger

from figma_flutter_agent.llm.prompts import (
    build_repair_system_prompt,
    render_escalated_metacognitive_repair_prompt,
)
from figma_flutter_agent.llm.repair_scope import RepairEnvironmentContext

MAX_ESCALATION_LEVELS: Final[int] = 4


class RepairPromptEscalator:
    """Maps repair loop attempts to progressively harsher system prompts."""

    def __init__(
        self,
        *,
        target_file: str,
        max_attempts: int,
    ) -> None:
        self.target_file = target_file.replace("\\", "/")
        self.max_attempts = max(1, min(max_attempts, MAX_ESCALATION_LEVELS))
        logger.bind(target_file=self.target_file, max_attempts=self.max_attempts).debug(
            "Repair prompt escalator ready"
        )

    def escalation_level(self, attempt: int) -> int:
        """Map loop attempt 1..max_attempts onto escalation levels 1..4."""
        if attempt < 1:
            msg = f"Invalid repair attempt: {attempt}"
            raise ValueError(msg)
        if self.max_attempts <= 1:
            return 1
        index = attempt - 1
        span = self.max_attempts - 1
        return min(MAX_ESCALATION_LEVELS, 1 + (index * (MAX_ESCALATION_LEVELS - 1)) // span)

    @staticmethod
    def tactical_directive_for_level(level: int, *, target_file: str) -> str:
        if level <= 1:
            return (
                "TACTICAL DIRECTIVE (LEVEL 1): Perform standard APR on the scoped repair targets. "
                f"Fix syntax tokens, imports, and parameter mismatches in `{target_file}` and "
                "any scoped extractedWidget files. Preserve Figma layout coordinates."
            )
        if level == 2:
            return (
                "TACTICAL DIRECTIVE (LEVEL 2): LOCAL REPAIR STAGNATION — CHANGE STRATEGY. "
                "The screen file patch loop failed to converge. STOP rewriting the same screen "
                "instantiation lines. Inspect `lib/widgets/` extractedWidget targets in "
                "repairTargets. FORCE PUBLIC WIDGET CONTRACTS: strip leading `_` from widget "
                "class names and align screenCode call sites with public PascalCase names from "
                "widgetName. Fix constructor signatures in widget files, not repeated screen tweaks."
            )
        if level == 3:
            return (
                "TACTICAL DIRECTIVE (LEVEL 3): SURGICAL UNIFIED DIFF — RESET PATCH STRATEGY. "
                "Prior patches failed because delimiters are corrupted. Emit git unified diffs "
                "only: one or more @@ hunks with 3+ context lines, fixing the exact line from "
                "focused error context. FORBIDDEN: full-file bodies, SEARCH/REPLACE, or "
                "<<<<<<< markers. Prefer multiple small hunks over one giant replacement."
            )
        return (
            "TACTICAL DIRECTIVE (LEVEL 4): EMERGENCY LAST STAND — FINAL ATTEMPT. "
            "Do not invent new architecture. Isolate the exact analyzer error line and apply a "
            "minimal surgical patch. You MAY wrap a failing subtree in SizedBox.shrink() or a "
            "neutral placeholder. The project MUST compile now. Output only FlutterRepairPatchResponse."
        )

    def generate_system_prompt(
        self,
        *,
        attempt: int,
        env_context: RepairEnvironmentContext,
        level: int | None = None,
    ) -> str:
        level = level if level is not None else self.escalation_level(attempt)
        if level <= 1:
            logger.info("Repair prompt escalation level 1 (standard APR)")
            return build_repair_system_prompt(env_context)
        logger.warning(
            "Repair prompt escalation level {} (metacognitive shift, attempt {}/{})",
            level,
            attempt,
            self.max_attempts,
        )
        directive = self.tactical_directive_for_level(level, target_file=self.target_file)
        return render_escalated_metacognitive_repair_prompt(
            env_context,
            escalation_level=level,
            tactical_directive=directive,
            target_file=self.target_file,
            attempt=attempt,
            max_attempts=self.max_attempts,
        )
