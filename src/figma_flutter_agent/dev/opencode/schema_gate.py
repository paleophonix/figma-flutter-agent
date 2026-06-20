"""JSON schema validation for repair pipeline step outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.errors import FigmaFlutterError, LlmError
from figma_flutter_agent.llm.clients.response import ResponseMixin

_SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"

_STEP_REQUIRED: dict[str, tuple[str, ...]] = {
    "recognise": ("step", "symptoms"),
    "inspect": ("step", "entities"),
    "diagnose": ("step", "laws"),
    "plan": ("step", "steps"),
    "repair": ("step",),
    "review": ("step", "decision", "reason_code"),
    "summarize": ("step",),
    "fix": ("step",),
    "check": ("step", "passed"),
    "capture": ("step", "passed"),
}


def load_step_schema(step: str) -> dict[str, Any]:
    """Load JSON schema file for a pipeline step."""
    path = _SCHEMAS_DIR / f"{step}.schema.json"
    if not path.is_file():
        return {"type": "object", "properties": {"step": {"type": "string"}}}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_step_json(raw: str, *, step: str) -> dict[str, Any]:
    """Parse repair step structured output from an LLM response body.

    Args:
        raw: Assistant message text (JSON or fenced JSON).
        step: Pipeline step name for error context.

    Returns:
        Parsed JSON object.

    Raises:
        LlmError: When the body is empty or not valid JSON.
    """
    coerced = ResponseMixin._coerce_json_text(raw)
    if not coerced:
        raise LlmError(f"Step {step} returned empty structured output")
    try:
        payload = json.loads(coerced)
    except json.JSONDecodeError as exc:
        preview = coerced[:240].replace("\n", "\\n")
        raise LlmError(
            f"Step {step} returned non-JSON structured output: {exc}; preview={preview!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise LlmError(f"Step {step} returned non-object JSON")
    return payload


def coerce_step_output(step: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Attach the orchestrator-owned step id when the model omits it.

    Args:
        step: Pipeline step name for this invocation.
        payload: Parsed LLM JSON object.

    Returns:
        Payload with a canonical ``step`` field.

    Raises:
        FigmaFlutterError: When the model reports a different step name.
    """
    if not isinstance(payload, dict):
        raise FigmaFlutterError(f"Step {step} output must be a JSON object")
    reported = payload.get("step")
    if reported in (None, ""):
        return {**payload, "step": step}
    if reported != step:
        raise FigmaFlutterError(f"Step field must be {step!r}, got {reported!r}")
    return payload


def validate_step_output(step: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate required fields for a step output.

    Args:
        step: Expected pipeline step name.
        payload: Parsed step JSON from the model.

    Returns:
        Canonicalized payload (``step`` injected when missing).

    Raises:
        FigmaFlutterError: When required fields are missing or step mismatches.
    """
    normalized = coerce_step_output(step, payload)
    required = _STEP_REQUIRED.get(step, ("step",))
    missing = [field for field in required if field not in normalized]
    if missing:
        raise FigmaFlutterError(f"Step {step} missing required fields: {', '.join(missing)}")
    return normalized


def structured_output_spec(step: str) -> tuple[str, dict[str, Any]]:
    """Return (name, schema) for OpenRouter structured output."""
    schema = load_step_schema(step)
    return f"repair_{step}", schema
