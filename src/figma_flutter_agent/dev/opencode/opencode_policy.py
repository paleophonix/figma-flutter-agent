"""Map ``debug_pipeline`` policy to OpenCode agent/model/reasoning options."""

from __future__ import annotations

import json
from typing import Any

from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig
from figma_flutter_agent.llm.reasoning import LlmReasoningEffort

OPENCODE_PROVIDER = "openrouter"
OPENCODE_REPAIR_AGENT = "repair"
OPENCODE_FIX_AGENT = "fix"

# Repair/fix gates run ruff+pytest in Python; deny bash to avoid token-heavy shell loops.
REPAIR_OPENCODE_PERMISSION: dict[str, Any] = {
    "edit": "allow",
    "read": "allow",
    "grep": "allow",
    "glob": "allow",
    "list": "allow",
    "bash": "deny",
    "task": "deny",
    "webfetch": "deny",
}

FIX_OPENCODE_PERMISSION: dict[str, Any] = {
    "edit": "allow",
    "read": "allow",
    "grep": "allow",
    "glob": "allow",
    "list": "allow",
    "bash": "deny",
    "task": "deny",
    "webfetch": "deny",
}


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
    permission: dict[str, Any] | None = None,
    steps: int | None = None,
) -> dict[str, Any]:
    """Build shared OpenCode agent fields for one model slug."""
    normalized = normalize_opencode_model(model)
    agent: dict[str, Any] = {
        "mode": "primary",
        "model": normalized,
        "permission": dict(permission or {"edit": "allow", "bash": "allow"}),
    }
    if steps is not None:
        agent["steps"] = steps
    effort_value = opencode_reasoning_effort_value(effort)
    if effort_value is not None:
        agent["reasoningEffort"] = effort_value
    return agent


def _provider_options_for_model_efforts(
    entries: tuple[tuple[str, LlmReasoningEffort], ...],
) -> dict[str, Any] | None:
    """Build OpenCode provider model options for one or more slug/effort pairs."""
    provider_models: dict[str, dict[str, Any]] = {}
    provider_id: str | None = None
    for slug, effort in entries:
        effort_value = opencode_reasoning_effort_value(effort)
        if effort_value is None:
            continue
        resolved_provider, model_id = split_opencode_model(slug)
        provider_id = provider_id or resolved_provider
        provider_models[model_id] = {"options": {"reasoningEffort": effort_value}}
    if not provider_models or provider_id is None:
        return None
    return {provider_id: {"models": provider_models}}


def _provider_options_for_models(
    models: tuple[str, ...],
    *,
    effort: LlmReasoningEffort,
) -> dict[str, Any] | None:
    """Build OpenCode provider model options for one or more slugs."""
    return _provider_options_for_model_efforts(tuple((slug, effort) for slug in models))


def _merge_openrouter_provider(
    overlay: dict[str, Any],
    *,
    openrouter_api_key: str | None,
    model_provider: dict[str, Any] | None,
) -> None:
    """Merge OpenRouter provider config without dropping ``apiKey``.

    OpenCode ``OPENCODE_CONFIG_CONTENT`` does not expand ``${VAR}`` placeholders;
    the literal ``apiKey`` must stay in the overlay whenever model effort options
    are also present.
    """
    if not openrouter_api_key and not model_provider:
        return
    provider = dict(overlay.get("provider") or {})
    if model_provider:
        for provider_id, provider_data in model_provider.items():
            merged = dict(provider.get(provider_id) or {})
            merged.update(provider_data)
            if openrouter_api_key and provider_id == OPENCODE_PROVIDER:
                merged["apiKey"] = openrouter_api_key
            provider[provider_id] = merged
    elif openrouter_api_key:
        openrouter = dict(provider.get(OPENCODE_PROVIDER) or {})
        openrouter["apiKey"] = openrouter_api_key
        provider[OPENCODE_PROVIDER] = openrouter
    overlay["provider"] = provider


def build_opencode_overlay(
    config: DebugPipelineConfig,
    *,
    openrouter_api_key: str | None = None,
) -> dict[str, Any]:
    """Build ``OPENCODE_CONFIG_CONTENT`` overlay from loaded pipeline policy."""
    repair_model = normalize_opencode_model(config.model_for_step("repair"))
    fix_model = normalize_opencode_model(config.model_for_step("fix"))
    repair_effort = config.effort_for_step("repair")
    fix_effort = config.effort_for_step("fix")

    overlay: dict[str, Any] = {
        "agent": {
            OPENCODE_REPAIR_AGENT: {
                **_agent_base(
                    repair_model,
                    effort=repair_effort,
                    permission=REPAIR_OPENCODE_PERMISSION,
                    steps=config.loops.max_opencode_repair_steps,
                ),
                "description": "Compiler repair build step (sandbox src/ + tests/)",
            },
            OPENCODE_FIX_AGENT: {
                **_agent_base(
                    fix_model,
                    effort=fix_effort,
                    permission=FIX_OPENCODE_PERMISSION,
                    steps=config.loops.max_opencode_fix_steps,
                ),
                "description": "Emit-layer fix (.repair/candidate/planned_files only)",
            },
        },
    }
    provider_entries: list[tuple[str, LlmReasoningEffort]] = [
        (repair_model, repair_effort),
        (fix_model, fix_effort),
    ]
    model_efforts: dict[str, LlmReasoningEffort] = {}
    for slug, step_effort in provider_entries:
        model_id = split_opencode_model(slug)[1]
        prior = model_efforts.get(model_id)
        if prior is not None and prior != step_effort:
            model_efforts = {}
            break
        model_efforts[model_id] = step_effort
    if model_efforts:
        slug_by_model = {split_opencode_model(slug)[1]: slug for slug, _ in provider_entries}
        provider = _provider_options_for_model_efforts(
            tuple((slug_by_model[model_id], effort) for model_id, effort in model_efforts.items()),
        )
        if provider is not None:
            _merge_openrouter_provider(
                overlay,
                openrouter_api_key=openrouter_api_key,
                model_provider=provider,
            )
    else:
        _merge_openrouter_provider(
            overlay,
            openrouter_api_key=openrouter_api_key,
            model_provider=None,
        )
    return overlay


def overlay_json(
    config: DebugPipelineConfig,
    *,
    openrouter_api_key: str | None = None,
) -> str:
    """Serialize overlay for ``OPENCODE_CONFIG_CONTENT``."""
    return json.dumps(
        build_opencode_overlay(config, openrouter_api_key=openrouter_api_key),
        separators=(",", ":"),
    )


def prompt_options_for_write_step(
    config: DebugPipelineConfig,
    *,
    step: str,
    board: str = "forensic",
    attempt_index: int = 0,
) -> dict[str, str | None]:
    """Return OpenCode ``prompt_message`` kwargs for repair/fix write steps."""
    agent = OPENCODE_REPAIR_AGENT if step == "repair" else OPENCODE_FIX_AGENT
    return {
        "agent": agent,
        "model": normalize_opencode_model(
            config.model_for_step(step, board=board),  # type: ignore[arg-type]
        ),
        "reasoning_effort": opencode_reasoning_effort_value(
            config.effort_for_step(step, attempt_index=attempt_index),  # type: ignore[arg-type]
        ),
    }
