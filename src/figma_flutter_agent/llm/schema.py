"""LLM response schema helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

from figma_flutter_agent.schemas import FlutterGenerationResponse, FlutterRepairPatchResponse


@dataclass(frozen=True)
class StructuredOutputSpec:
    """Provider-agnostic structured output contract."""

    name: str
    schema: dict[str, Any]
    anthropic_tool_name: str
    anthropic_tool_description: str


def _normalize_strict_schema(node: Any) -> Any:
    """Recursively normalize JSON schema for strict structured output providers."""
    if not isinstance(node, dict):
        return node

    normalized = deepcopy(node)
    node_type = normalized.get("type")

    if node_type == "object":
        normalized["additionalProperties"] = False
        properties = normalized.get("properties")
        if isinstance(properties, dict) and properties:
            normalized["required"] = list(properties.keys())

    for key in ("properties", "$defs", "definitions"):
        value = normalized.get(key)
        if isinstance(value, dict):
            normalized[key] = {
                name: _normalize_strict_schema(schema) for name, schema in value.items()
            }

    for key in ("items", "anyOf", "oneOf", "allOf"):
        value = normalized.get(key)
        if isinstance(value, list):
            normalized[key] = [_normalize_strict_schema(item) for item in value]
        elif isinstance(value, dict):
            normalized[key] = _normalize_strict_schema(value)

    return normalized


def generation_json_schema(*, strict: bool = True) -> dict[str, Any]:
    """Return JSON schema for structured codegen output across LLM providers.

    Args:
        strict: When True, normalize the schema for grammar-constrained output.

    Returns:
        JSON schema dictionary suitable for Anthropic, OpenAI, and Google Gemini structured output.
    """
    schema = FlutterGenerationResponse.model_json_schema()
    if not strict:
        return schema
    return cast(dict[str, Any], _normalize_strict_schema(schema))


def repair_patch_json_schema(*, strict: bool = True) -> dict[str, Any]:
    """Return JSON schema for scoped analyze repair patch output."""
    schema = FlutterRepairPatchResponse.model_json_schema()
    if not strict:
        return schema
    return cast(dict[str, Any], _normalize_strict_schema(schema))


def generation_output_spec(*, strict: bool = True) -> StructuredOutputSpec:
    """Return the default structured output spec for initial codegen."""
    return StructuredOutputSpec(
        name="flutter_generation_response",
        schema=generation_json_schema(strict=strict),
        anthropic_tool_name="emit_flutter_generation",
        anthropic_tool_description="Emit structured Flutter screen and widget generation output.",
    )


def repair_patch_output_spec(*, strict: bool = True) -> StructuredOutputSpec:
    """Return the structured output spec for scoped analyze repair."""
    return StructuredOutputSpec(
        name="flutter_repair_patch_response",
        schema=repair_patch_json_schema(strict=strict),
        anthropic_tool_name="emit_flutter_repair_patches",
        anthropic_tool_description="Emit scoped Dart repair patches for analyzer failures.",
    )
