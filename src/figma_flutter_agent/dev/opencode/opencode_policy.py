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


def build_opencode_overlay(config: DebugPipelineConfig) -> dict[str, Any]:
    """Build ``OPENCODE_CONFIG_CONTENT`` overlay from loaded pipeline policy."""
    model = normalize_opencode_model(config.models.single)
    provider_id, model_id = split_opencode_model(model)
    effort = opencode_reasoning_effort_value(config.effort)

    agent_base: dict[str, Any] = {
        "mode": "primary",
        "model": model,
        "permission": {"edit": "allow", "bash": "allow"},
    }
    if effort is not None:
        agent_base["reasoningEffort"] = effort

    overlay: dict[str, Any] = {
        "agent": {
            OPENCODE_REPAIR_AGENT: {
                **agent_base,
                "description": "Compiler repair build step (sandbox src/ + tests/)",
            },
            OPENCODE_FIX_AGENT: {
                **agent_base,
                "description": "Emit-layer fix (.repair/candidate/planned_files only)",
            },
        },
    }
    if effort is not None:
        overlay["provider"] = {
            provider_id: {
                "models": {
                    model_id: {
                        "options": {"reasoningEffort": effort},
                    },
                },
            },
        }
    return overlay


def overlay_json(config: DebugPipelineConfig) -> str:
    """Serialize overlay for ``OPENCODE_CONFIG_CONTENT``."""
    return json.dumps(build_opencode_overlay(config), separators=(",", ":"))


def prompt_options_for_write_step(
    config: DebugPipelineConfig,
    *,
    step: str,
) -> dict[str, str | None]:
    """Return OpenCode ``prompt_message`` kwargs for repair/fix write steps."""
    agent = OPENCODE_REPAIR_AGENT if step == "repair" else OPENCODE_FIX_AGENT
    return {
        "agent": agent,
        "model": normalize_opencode_model(config.models.single),
        "reasoning_effort": opencode_reasoning_effort_value(config.effort),
    }
