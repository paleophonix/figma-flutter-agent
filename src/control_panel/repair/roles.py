"""Epistemic diagnostician roles for parallel fan-out."""

from __future__ import annotations

EPISTEMIC_ROLES: tuple[str, ...] = (
    "skeptic",
    "empiric",
    "architect",
    "pragmatist",
    "devil",
)

ROLE_AGENT_MAP: dict[str, str] = {
    "skeptic": "diagnose-skeptic",
    "empiric": "diagnose-empiric",
    "architect": "diagnose-architect",
    "pragmatist": "diagnose-pragmatist",
    "devil": "diagnose-devil",
}

ROLE_PREAMBLE: dict[str, str] = {
    "skeptic": "You are the Skeptic. Challenge assumptions; list contradictions in evidence.",
    "empiric": "You are the Empiric. Ground claims in dart-errors, logs, and measurable facts.",
    "architect": "You are the Architect. Map failures to compiler layers and named laws.",
    "pragmatist": "You are the Pragmatist. Propose minimal universal fix scope in src/figma_flutter_agent.",
    "devil": "You are the Devil's advocate. Argue against repair; surface escalation risks.",
}


def role_prompt_slice(role: str, ticket_json: str) -> str:
    """Build diagnostician prompt for one epistemic role."""
    preamble = ROLE_PREAMBLE.get(role, f"You are diagnose-{role}.")
    return (
        f"{preamble}\n\n"
        "Load the diagnose skill if available. Output JSON with keys: "
        "root_cause, confidence (0-1), recommended_law, escalate (bool).\n\n"
        f"RepairTicket:\n{ticket_json}"
    )
