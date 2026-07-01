"""Tests for debug_pipeline → OpenCode policy mapping."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig
from figma_flutter_agent.dev.opencode.client import OpenCodeClient
from figma_flutter_agent.dev.opencode.opencode_policy import (
    OPENCODE_FIX_AGENT,
    OPENCODE_REPAIR_AGENT,
    build_opencode_overlay,
    normalize_opencode_model,
    prompt_options_for_write_step,
    split_opencode_model,
)
from figma_flutter_agent.dev.opencode.runtime import ensure_opencode_serve


def test_normalize_opencode_model_prefixes_openrouter_slug() -> None:
    assert normalize_opencode_model("deepseek/deepseek-v4-pro") == (
        "openrouter/deepseek/deepseek-v4-pro"
    )
    assert normalize_opencode_model("openrouter/fusion") == "openrouter/fusion"


def test_split_opencode_model() -> None:
    assert split_opencode_model("deepseek/deepseek-v4-pro") == (
        "openrouter",
        "deepseek/deepseek-v4-pro",
    )


def test_build_opencode_overlay_from_debug_pipeline() -> None:
    config = DebugPipelineConfig(
        effort="high",
        common_effort=True,
        models={"single": "deepseek/deepseek-v4-pro"},
    )
    overlay = build_opencode_overlay(config)
    assert overlay["agent"][OPENCODE_REPAIR_AGENT]["reasoningEffort"] == "high"
    assert overlay["agent"][OPENCODE_REPAIR_AGENT]["steps"] == 10
    assert overlay["agent"][OPENCODE_REPAIR_AGENT]["permission"]["bash"] == "deny"
    assert overlay["agent"][OPENCODE_FIX_AGENT]["model"] == "openrouter/deepseek/deepseek-v4-pro"
    assert overlay["provider"]["openrouter"]["models"]["deepseek/deepseek-v4-pro"]["options"] == {
        "reasoningEffort": "high",
    }


def test_build_opencode_overlay_preserves_api_key_with_model_efforts() -> None:
    config = DebugPipelineConfig(
        effort="high",
        common_effort=True,
        models={"single": "deepseek/deepseek-v4-pro"},
    )
    overlay = build_opencode_overlay(config, openrouter_api_key="sk-or-test")
    openrouter = overlay["provider"]["openrouter"]
    assert openrouter["apiKey"] == "sk-or-test"
    assert openrouter["models"]["deepseek/deepseek-v4-pro"]["options"] == {
        "reasoningEffort": "high",
    }


def test_build_opencode_overlay_uses_per_step_effort_by_default() -> None:
    config = DebugPipelineConfig(models={"single": "deepseek/deepseek-v4-pro"})
    overlay = build_opencode_overlay(config)
    assert "reasoningEffort" not in overlay["agent"][OPENCODE_REPAIR_AGENT]
    assert "reasoningEffort" not in overlay["agent"][OPENCODE_FIX_AGENT]
    assert "provider" not in overlay


def test_build_opencode_overlay_omits_reasoning_when_none() -> None:
    config = DebugPipelineConfig(effort="none", common_effort=True)
    overlay = build_opencode_overlay(config)
    assert "reasoningEffort" not in overlay["agent"][OPENCODE_REPAIR_AGENT]
    assert "provider" not in overlay


def test_prompt_options_for_write_steps() -> None:
    config = DebugPipelineConfig(
        effort="low",
        common_effort=True,
        models={
            "single": "custom/vendor-model",
            "per_step": {
                "repair": "xiaomi/mimo-v2.5-pro",
                "fix": "xiaomi/mimo-v2.5-pro",
            },
        },
    )
    repair = prompt_options_for_write_step(config, step="repair")
    fix = prompt_options_for_write_step(config, step="fix")
    assert repair["agent"] == OPENCODE_REPAIR_AGENT
    assert fix["agent"] == OPENCODE_FIX_AGENT
    assert repair["model"] == "openrouter/xiaomi/mimo-v2.5-pro"
    assert fix["model"] == "openrouter/xiaomi/mimo-v2.5-pro"
    assert repair["reasoning_effort"] == "low"
    assert fix["reasoning_effort"] == "low"


def test_prompt_options_use_per_step_effort_defaults() -> None:
    config = DebugPipelineConfig(
        models={
            "single": "custom/vendor-model",
            "per_step": {
                "repair": "xiaomi/mimo-v2.5-pro",
                "fix": "xiaomi/mimo-v2.5-pro",
            },
        },
    )
    repair = prompt_options_for_write_step(config, step="repair")
    fix = prompt_options_for_write_step(config, step="fix")
    assert repair["reasoning_effort"] is None
    assert fix["reasoning_effort"] is None
    retry_repair = prompt_options_for_write_step(config, step="repair", attempt_index=1)
    assert retry_repair["reasoning_effort"] == "low"


def test_build_opencode_overlay_uses_per_step_models() -> None:
    config = DebugPipelineConfig(
        models={
            "single": "deepseek/deepseek-v4-pro",
            "per_step": {
                "repair": "xiaomi/mimo-v2.5-pro",
                "fix": "xiaomi/mimo-v2.5-pro",
            },
        },
    )
    overlay = build_opencode_overlay(config)
    assert overlay["agent"][OPENCODE_REPAIR_AGENT]["model"] == ("openrouter/xiaomi/mimo-v2.5-pro")
    assert overlay["agent"][OPENCODE_FIX_AGENT]["model"] == "openrouter/xiaomi/mimo-v2.5-pro"


@pytest.mark.asyncio
async def test_prompt_message_includes_reasoning_effort() -> None:
    client = OpenCodeClient(base_url="http://127.0.0.1:4096")
    captured: dict[str, object] = {}

    async def _fake_post(*_args: object, **kwargs: object) -> MagicMock:
        captured["json"] = kwargs.get("json")
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value={"parts": []})
        return response

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=_fake_post)):
        await client.prompt_message(
            "sess-1",
            text="hello",
            agent="repair",
            model="deepseek/deepseek-v4-pro",
            reasoning_effort="high",
        )

    body = captured["json"]
    assert isinstance(body, dict)
    assert body["agent"] == "repair"
    assert body["reasoningEffort"] == "high"
    assert body["model"] == {
        "providerID": "openrouter",
        "modelID": "deepseek/deepseek-v4-pro",
    }


@pytest.mark.asyncio
async def test_spawn_opencode_serve_passes_config_overlay_env() -> None:
    overlay = build_opencode_overlay(DebugPipelineConfig())
    proc = MagicMock()
    proc.poll.return_value = None

    with (
        patch(
            "figma_flutter_agent.dev.opencode.runtime.OpenCodeClient",
        ) as client_cls,
        patch(
            "figma_flutter_agent.dev.opencode.runtime._spawn_opencode_serve",
        ) as spawn,
        patch("figma_flutter_agent.dev.opencode.runtime._spawned_process", None),
        patch("figma_flutter_agent.dev.opencode.runtime.asyncio.sleep", new=AsyncMock()),
    ):
        client_cls.return_value.health = AsyncMock(side_effect=[None, {"ok": True}])
        spawn.return_value = proc
        await ensure_opencode_serve(
            base_url="http://127.0.0.1:4096",
            config_overlay=overlay,
            timeout_sec=5.0,
        )

    spawn.assert_called_once_with(
        hostname="127.0.0.1",
        port=4096,
        config_overlay=overlay,
        openrouter_api_key=None,
    )


@pytest.mark.asyncio
async def test_spawn_opencode_serve_serializes_overlay_in_subprocess_env() -> None:
    overlay = {"agent": {"repair": {"reasoningEffort": "high"}}}
    with (
        patch("figma_flutter_agent.dev.opencode.runtime.shutil.which", return_value="opencode"),
        patch("figma_flutter_agent.dev.opencode.runtime.subprocess.Popen") as popen,
    ):
        from figma_flutter_agent.dev.opencode.runtime import _spawn_opencode_serve

        _spawn_opencode_serve(hostname="127.0.0.1", port=4096, config_overlay=overlay)
        env = popen.call_args.kwargs["env"]
        assert json.loads(env["OPENCODE_CONFIG_CONTENT"]) == overlay
