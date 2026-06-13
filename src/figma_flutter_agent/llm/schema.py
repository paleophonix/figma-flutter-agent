"""LLM response schema helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

from figma_flutter_agent.schemas import (
    FlutterGenerationResponse,
    FlutterRepairPatchResponse,
    RepairCpiSupervisorResponse,
)


@dataclass(frozen=True)
class StructuredOutputSpec:
    """Provider-agnostic structured output contract."""

    name: str
    schema: dict[str, Any]
    anthropic_tool_name: str
    anthropic_tool_description: str


def _object_uses_dynamic_additional_properties(node: dict[str, Any]) -> bool:
    additional = node.get("additionalProperties")
    if additional is True:
        return True
    return isinstance(additional, dict)


def _is_openai_incompatible_map_property(prop: Any) -> bool:
    """OpenAI strict mode rejects object maps (only ``additionalProperties: false``)."""
    if not isinstance(prop, dict):
        return False
    return (
        prop.get("type") == "object"
        and "properties" not in prop
        and _object_uses_dynamic_additional_properties(prop)
    )


def _strip_ref_sibling_keywords(node: Any) -> Any:
    """OpenAI strict mode rejects keywords alongside ``$ref``."""
    if isinstance(node, list):
        return [_strip_ref_sibling_keywords(item) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return {"$ref": node["$ref"]}
    return {key: _strip_ref_sibling_keywords(value) for key, value in node.items()}


def _anyof_branch_has_type(branch: Any) -> bool:
    if not isinstance(branch, dict):
        return True
    if "$ref" in branch:
        return True
    if "type" in branch:
        return True
    if "anyOf" in branch or "oneOf" in branch or "allOf" in branch:
        return True
    return False


def _coerce_untyped_schema_branch(branch: dict[str, Any]) -> dict[str, Any]:
    """Replace Pydantic ``Any`` `{}` branches with OpenAI-compatible scalar unions."""
    if branch != {}:
        return branch
    return {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
            {"type": "number"},
            {"type": "boolean"},
        ]
    }


def _normalize_strict_schema(node: Any) -> Any:
    """Recursively normalize JSON schema for strict structured output providers."""
    if not isinstance(node, dict):
        return node

    normalized = deepcopy(node)

    for key in ("properties", "$defs", "definitions"):
        value = normalized.get(key)
        if isinstance(value, dict):
            normalized[key] = {
                name: _normalize_strict_schema(schema) for name, schema in value.items()
            }

    for key in ("items", "anyOf", "oneOf", "allOf"):
        value = normalized.get(key)
        if isinstance(value, list):
            normalized[key] = [
                _coerce_untyped_schema_branch(item)
                if isinstance(item, dict) and not _anyof_branch_has_type(item)
                else _normalize_strict_schema(item)
                for item in value
            ]
        elif isinstance(value, dict):
            normalized[key] = _normalize_strict_schema(value)

    if normalized.get("type") == "object":
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            filtered = {
                name: prop_schema
                for name, prop_schema in properties.items()
                if not _is_openai_incompatible_map_property(prop_schema)
            }
            normalized["properties"] = filtered
            if filtered:
                normalized["required"] = list(filtered.keys())
                if not _object_uses_dynamic_additional_properties(normalized):
                    normalized["additionalProperties"] = False
            else:
                normalized.pop("required", None)

    return _strip_ref_sibling_keywords(normalized)


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


def cpi_supervisor_json_schema(*, strict: bool = True) -> dict[str, Any]:
    """Return JSON schema for repair-loop CPI supervisor output."""
    schema = RepairCpiSupervisorResponse.model_json_schema()
    if not strict:
        return schema
    return cast(dict[str, Any], _normalize_strict_schema(schema))


def cpi_supervisor_output_spec(*, strict: bool = True) -> StructuredOutputSpec:
    """Return the structured output spec for CPI loop-supervisor escalation."""
    return StructuredOutputSpec(
        name="repair_cpi_supervisor_response",
        schema=cpi_supervisor_json_schema(strict=strict),
        anthropic_tool_name="emit_repair_cpi_supervisor",
        anthropic_tool_description=(
            "Emit metacognitive analysis and a pattern-interrupt directive for a stuck repair loop."
        ),
    )
