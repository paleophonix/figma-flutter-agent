"""Diagnose output validation for the repair read pipeline."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.errors import FigmaFlutterError

_COMPILER_PREFIX = "src/figma_flutter_agent/"


def inspect_anchors_compiler_surfaces(chain: ReasoningChain) -> bool:
    """Return True when inspect entities name compiler repo paths."""
    inspect = chain.steps.get("inspect")
    if not isinstance(inspect, dict):
        return False
    for entity in inspect.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        for raw in entity.get("repoPaths") or []:
            path = str(raw).strip().replace("\\", "/")
            if path.startswith(_COMPILER_PREFIX):
                return True
    return False


def diagnose_laws_missing(diagnose: dict[str, object], chain: ReasoningChain) -> bool:
    """Return True when diagnose must have laws but returned an empty list."""
    if not isinstance(diagnose, dict) or diagnose.get("blocked"):
        return False
    laws = diagnose.get("laws")
    if isinstance(laws, list) and laws:
        return False
    return inspect_anchors_compiler_surfaces(chain)


def validate_diagnose_output(diagnose: dict[str, object], chain: ReasoningChain) -> None:
    """Require laws when inspect anchored compiler surfaces.

    Args:
        diagnose: Parsed diagnose step JSON.
        chain: Cumulative reasoning chain including inspect output.

    Raises:
        FigmaFlutterError: When diagnose omitted required laws[] entries.
    """
    if diagnose_laws_missing(diagnose, chain):
        raise FigmaFlutterError(
            "diagnose blocked: laws[] is empty but inspect.entities include "
            f"{_COMPILER_PREFIX} repoPaths; emit at least one P0 compiler law "
            "(recognise.blocked does not excuse empty laws on FORENSIC board)."
        )


def terminal_blocked_plan_for_empty_diagnose(
    *,
    diagnose: dict[str, object],
    validation_error: str,
) -> dict[str, object]:
    """Build a deterministic executive plan when diagnose cannot produce laws."""
    return {
        "step": "plan",
        "steps": [],
        "blocked": True,
        "blockedItems": [
            {
                "lawId": "diagnose_empty_laws",
                "reason": validation_error,
                "missing_evidence": "diagnose.laws[] after inspect compiler anchors",
            }
        ],
        "notes": "Orchestrator terminal plan: diagnose produced no laws.",
    }
