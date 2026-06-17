"""RepairTicket schema and GitLab markdown rendering."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from figma_flutter_agent.llm.schema import StructuredOutputSpec


class FailureFamily(StrEnum):
    """High-level compiler failure classification."""

    PARSE = "parse"
    IR = "ir"
    EMIT = "emit"
    DART = "dart"
    SEMANTIC = "semantic"
    FIDELITY = "fidelity"
    UNKNOWN = "unknown"


class RepairEvidence(BaseModel):
    """Pointer to a processed artifact fact."""

    file: str
    pointer: str = ""
    quote: str = ""


class SuspectedLayer(BaseModel):
    """Ordered layer hypothesis with confidence."""

    layer: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class RepairTicket(BaseModel):
    """Structured repair context produced after the Context stage."""

    symptom_summary: str
    failure_family: FailureFamily
    suspected_layers: list[SuspectedLayer] = Field(default_factory=list)
    evidence: list[RepairEvidence] = Field(default_factory=list)
    layout_hazards: list[str] = Field(default_factory=list)
    repair_scope: str = "src/figma_flutter_agent and relevant tests/"
    escalate_to_human: bool = False
    escalate_reason: str = ""
    artifact_pointers: list[str] = Field(default_factory=list)
    visual_hints: list[str] = Field(default_factory=list)
    include_raw_fallback: bool = False


def repair_ticket_output_spec(*, strict: bool = True) -> StructuredOutputSpec:
    """JSON schema for context-stage LLM output."""
    schema = {
        "type": "object",
        "properties": {
            "symptom_summary": {"type": "string"},
            "failure_family": {
                "type": "string",
                "enum": [item.value for item in FailureFamily],
            },
            "suspected_layers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "layer": {"type": "string"},
                        "confidence": {"type": "number"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["layer", "confidence"],
                    "additionalProperties": False,
                },
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "pointer": {"type": "string"},
                        "quote": {"type": "string"},
                    },
                    "required": ["file"],
                    "additionalProperties": False,
                },
            },
            "layout_hazards": {"type": "array", "items": {"type": "string"}},
            "repair_scope": {"type": "string"},
            "escalate_to_human": {"type": "boolean"},
            "escalate_reason": {"type": "string"},
            "artifact_pointers": {"type": "array", "items": {"type": "string"}},
            "visual_hints": {"type": "array", "items": {"type": "string"}},
            "include_raw_fallback": {"type": "boolean"},
        },
        "required": [
            "symptom_summary",
            "failure_family",
            "suspected_layers",
            "evidence",
            "escalate_to_human",
        ],
        "additionalProperties": False,
    }
    return StructuredOutputSpec(
        name="repair_ticket",
        schema=schema,
        anthropic_tool_name="repair_ticket",
        anthropic_tool_description="Structured repair ticket for compiler auto-repair.",
    )


def render_ticket_markdown(ticket: RepairTicket, *, repair_job_id: str) -> str:
    """Render a human-readable GitLab issue comment body."""
    lines = [
        f"## Repair ticket `{repair_job_id}`",
        "",
        ticket.symptom_summary,
        "",
        f"**Failure family:** `{ticket.failure_family.value}`",
        "",
    ]
    if ticket.suspected_layers:
        lines.append("**Suspected layers:**")
        for layer in ticket.suspected_layers:
            lines.append(
                f"- `{layer.layer}` ({layer.confidence:.0%}) — {layer.rationale}".rstrip()
            )
        lines.append("")
    if ticket.evidence:
        lines.append("**Evidence:**")
        for item in ticket.evidence[:8]:
            quote = f' — "{item.quote[:200]}"' if item.quote else ""
            lines.append(f"- `{item.file}`{quote}")
        lines.append("")
    if ticket.layout_hazards:
        lines.append("**Layout hazards:** " + "; ".join(ticket.layout_hazards[:6]))
        lines.append("")
    if ticket.escalate_to_human:
        lines.append(f"**Escalate to human:** {ticket.escalate_reason or 'yes'}")
        lines.append("")
    lines.append(f"**Scope:** {ticket.repair_scope}")
    return "\n".join(lines).strip()
