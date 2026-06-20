"""Map ``debug_pipeline`` policy to OpenCode agent/model/reasoning options."""

from __future__ import annotations

import json
from typing import Any

from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig
from figma_flutter_agent.llm.reasoning import LlmReasoningEffort

OPENCODE_PROVIDER = "openrouter"
OPENCODE_REPAIR_AGENT = "repair"
OPENCODE_FIX_AGENT = "fix"


def normalize_opencode_model(slug: str) -> str:
    """Return ``provider/model`` slug understood by OpenCode."""
    normalized = slug.strip()
    if not normalized:
        msg = "OpenCode model slug must be non-empty"
        raise ValueError(msg)
    if "/" not in normalized:
        return f"{OPENCODE_PROVIDER}/{normalized}"
    provider, _, model_id = normalized.partition("/")
    if provider == OPENCODE_PROVIDER:
        return normalized
    if model_id and provider not in {OPENCODE_PROVIDER, "openai", "anthropic", "google"}:
        return f"{OPENCODE_PROVIDER}/{normalized}"
    return normalized


def split_opencode_model(slug: str) -> tuple[str, str]:
    """Split an OpenCode model slug into provider id and model id."""
    normalized = normalize_opencode_model(slug)
    provider_id, _, model_id = normalized.partition("/")
    if not model_id:
        msg = f"invalid OpenCode model slug: {slug!r}"
        raise ValueError(msg)
    return provider_id, model_id


def opencode_reasoning_effort_value(effort: LlmReasoningEffort) -> str | None:
    """Return OpenCode ``reasoningEffort`` or ``None`` when reasoning is off."""
    if effort == "none":
        return None
    return effort


def _agent_base(
    model: str,
    *,
    effort: LlmReasoningEffort,
) -> dict[str, Any]:
    """Build shared OpenCode agent fields for one model slug."""
    normalized = normalize_opencode_model(model)
    agent: dict[str, Any] = {
        "mode": "primary",
        "model": normalized,
        "permission": {"edit": "allow", "bash": "allow"},
    }
    effort_value = opencode_reasoning_effort_value(effort)
    if effort_value is not None:
        agent["reasoningEffort"] = effort_value
    return agent


def _provider_options_for_models(
    models: tuple[str, ...],
    *,
    effort: LlmReasoningEffort,
) -> dict[str, Any] | None:
    """Build OpenCode provider model options for one or more slugs."""
    effort_value = opencode_reasoning_effort_value(effort)
    if effort_value is None:
        return None
    provider_models: dict[str, dict[str, Any]] = {}
    for slug in models:
        provider_id, model_id = split_opencode_model(slug)
        provider_models[model_id] = {"options": {"reasoningEffort": effort_value}}
    provider_id = split_opencode_model(models[0])[0]
    return {provider_id: {"models": provider_models}}


def build_opencode_overlay(config: DebugPipelineConfig) -> dict[str, Any]:
    """Build ``OPENCODE_CONFIG_CONTENT`` overlay from loaded pipeline policy."""
    repair_model = normalize_opencode_model(config.model_for_step("repair"))
    fix_model = normalize_opencode_model(config.model_for_step("fix"))
    effort = config.effort

    overlay: dict[str, Any] = {
        "agent": {
            OPENCODE_REPAIR_AGENT: {
                **_agent_base(repair_model, effort=effort),
                "description": "Compiler repair build step (sandbox src/ + tests/)",
            },
            OPENCODE_FIX_AGENT: {
                **_agent_base(fix_model, effort=effort),
                "description": "Emit-layer fix (.repair/candidate/planned_files only)",
            },
        },
    }
    unique_models = tuple(dict.fromkeys((repair_model, fix_model)))
    provider = _provider_options_for_models(unique_models, effort=effort)
    if provider is not None:
        overlay["provider"] = provider
    return overlay


def overlay_json(config: DebugPipelineConfig) -> str:
    """Serialize overlay for ``OPENCODE_CONFIG_CONTENT``."""
    return json.dumps(build_opencode_overlay(config), separators=(",", ":"))


def prompt_options_for_write_step(
    config: DebugPipelineConfig,
    *,
    step: str,
    board: str = "forensic",
) -> dict[str, str | None]:
    """Return OpenCode ``prompt_message`` kwargs for repair/fix write steps."""
    agent = OPENCODE_REPAIR_AGENT if step == "repair" else OPENCODE_FIX_AGENT
    return {
        "agent": agent,
        "model": normalize_opencode_model(
            config.model_for_step(step, board=board),  # type: ignore[arg-type]
        ),
        "reasoning_effort": opencode_reasoning_effort_value(config.effort),
    }
