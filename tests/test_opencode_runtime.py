"""Tests for OpenCode serve bootstrap."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from figma_flutter_agent.dev.opencode.client import parse_serve_host_port
from figma_flutter_agent.dev.opencode.runtime import ensure_opencode_serve
from figma_flutter_agent.errors import FigmaFlutterError


def test_parse_serve_host_port_defaults() -> None:
    host, port = parse_serve_host_port("http://127.0.0.1:4096")
    assert host == "127.0.0.1"
    assert port == 4096


@pytest.mark.asyncio
async def test_ensure_opencode_serve_skips_spawn_when_healthy_without_overlay() -> None:
    with patch(
        "figma_flutter_agent.dev.opencode.runtime.OpenCodeClient",
    ) as client_cls:
        client = client_cls.return_value
        client.health = AsyncMock(return_value={"ok": True})

        status = await ensure_opencode_serve(base_url="http://127.0.0.1:4096")

    assert status.started_locally is False
    assert status.restarted is False
    assert status.health == {"ok": True}


@pytest.mark.asyncio
async def test_ensure_opencode_serve_restarts_when_overlay_required() -> None:
    health_mock = AsyncMock(side_effect=[{"ok": True}, None, {"ok": True}])
    proc = MagicMock()
    proc.poll.return_value = None

    with (
        patch(
            "figma_flutter_agent.dev.opencode.runtime.OpenCodeClient",
        ) as client_cls,
        patch(
            "figma_flutter_agent.dev.opencode.runtime.stop_listeners_on_port",
            return_value=[40020],
        ) as stop,
        patch(
            "figma_flutter_agent.dev.opencode.runtime._spawn_opencode_serve",
            return_value=proc,
        ) as spawn,
        patch("figma_flutter_agent.dev.opencode.runtime._spawned_process", None),
        patch("figma_flutter_agent.dev.opencode.runtime.asyncio.sleep", new=AsyncMock()),
    ):
        client_cls.return_value.health = health_mock
        status = await ensure_opencode_serve(
            base_url="http://127.0.0.1:4096",
            timeout_sec=5.0,
            config_overlay={"agent": {"repair": {"steps": 16}}},
            openrouter_api_key="test-key",
        )

    stop.assert_called_once_with(4096)
    spawn.assert_called_once()
    assert status.started_locally is True
    assert status.restarted is True


@pytest.mark.asyncio
async def test_ensure_opencode_serve_respawns_after_restart_even_if_still_healthy() -> None:
    health_mock = AsyncMock(return_value={"ok": True})
    proc = MagicMock()
    proc.poll.return_value = None

    with (
        patch(
            "figma_flutter_agent.dev.opencode.runtime.OpenCodeClient",
        ) as client_cls,
        patch(
            "figma_flutter_agent.dev.opencode.runtime.stop_listeners_on_port",
            return_value=[40020],
        ) as stop,
        patch(
            "figma_flutter_agent.dev.opencode.runtime._spawn_opencode_serve",
            return_value=proc,
        ) as spawn,
        patch("figma_flutter_agent.dev.opencode.runtime._spawned_process", None),
        patch("figma_flutter_agent.dev.opencode.runtime.asyncio.sleep", new=AsyncMock()),
    ):
        client_cls.return_value.health = health_mock
        status = await ensure_opencode_serve(
            base_url="http://127.0.0.1:4096",
            timeout_sec=5.0,
            config_overlay={"agent": {"repair": {"steps": 16}}},
            openrouter_api_key="test-key",
        )

    stop.assert_called_once_with(4096)
    spawn.assert_called_once()
    assert status.started_locally is True
    assert status.restarted is True


@pytest.mark.asyncio
async def test_ensure_opencode_serve_spawns_and_polls() -> None:
    health_mock = AsyncMock(side_effect=[None, None, {"ok": True}])
    proc = MagicMock()
    proc.poll.return_value = None

    with (
        patch(
            "figma_flutter_agent.dev.opencode.runtime.OpenCodeClient",
        ) as client_cls,
        patch(
            "figma_flutter_agent.dev.opencode.runtime._spawn_opencode_serve",
            return_value=proc,
        ) as spawn,
        patch("figma_flutter_agent.dev.opencode.runtime._spawned_process", None),
        patch("figma_flutter_agent.dev.opencode.runtime.asyncio.sleep", new=AsyncMock()),
    ):
        client_cls.return_value.health = health_mock
        status = await ensure_opencode_serve(
            base_url="http://127.0.0.1:4096",
            timeout_sec=5.0,
        )

    spawn.assert_called_once_with(
        hostname="127.0.0.1",
        port=4096,
        config_overlay=None,
        openrouter_api_key=None,
    )
    assert status.started_locally is True
    assert status.restarted is False
    assert status.health == {"ok": True}


@pytest.mark.asyncio
async def test_ensure_opencode_serve_timeout_raises() -> None:
    with (
        patch(
            "figma_flutter_agent.dev.opencode.runtime.OpenCodeClient",
        ) as client_cls,
        patch(
            "figma_flutter_agent.dev.opencode.runtime._spawn_opencode_serve",
            return_value=MagicMock(poll=MagicMock(return_value=None)),
        ),
        patch("figma_flutter_agent.dev.opencode.runtime._spawned_process", None),
        patch("figma_flutter_agent.dev.opencode.runtime.asyncio.sleep", new=AsyncMock()),
        patch("figma_flutter_agent.dev.opencode.runtime.time.monotonic", side_effect=[0.0, 31.0]),
    ):
        client_cls.return_value.health = AsyncMock(return_value=None)

        with pytest.raises(FigmaFlutterError, match="did not become healthy"):
            await ensure_opencode_serve(base_url="http://127.0.0.1:4096", timeout_sec=30.0)
