"""JSON schema validation for repair pipeline step outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.errors import FigmaFlutterError

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


def validate_step_output(step: str, payload: dict[str, Any]) -> None:
    """Validate required fields for a step output.

    Raises:
        FigmaFlutterError: When required fields are missing or step mismatches.
    """
    if not isinstance(payload, dict):
        raise FigmaFlutterError(f"Step {step} output must be a JSON object")
    if payload.get("step") != step:
        raise FigmaFlutterError(f"Step field must be {step!r}, got {payload.get('step')!r}")
    required = _STEP_REQUIRED.get(step, ("step",))
    missing = [field for field in required if field not in payload]
    if missing:
        raise FigmaFlutterError(f"Step {step} missing required fields: {', '.join(missing)}")


def structured_output_spec(step: str) -> tuple[str, dict[str, Any]]:
    """Return (name, schema) for OpenRouter structured output."""
    schema = load_step_schema(step)
    return f"repair_{step}", schema
