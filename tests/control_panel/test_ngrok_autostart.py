"""Tests for control panel ngrok autostart helpers."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from control_panel.config.models import DiscordBotSettings, DiscordBotYamlConfig, InternalConfig
from control_panel.services import ngrok


def _settings(
    *,
    control_panel_url: str,
    webhook_bind: str = "127.0.0.1:8787",
    yaml_control_panel_url: str = "",
) -> DiscordBotSettings:
    return DiscordBotSettings(
        yaml=DiscordBotYamlConfig(
            internal=InternalConfig(
                control_panel_url=control_panel_url,
                webhook_bind=webhook_bind,
            ),
        ),
        yaml_control_panel_url=yaml_control_panel_url or control_panel_url,
        discord_bot_token="",
        gitlab_private_token="",
        github_token="",
        telegram_bot_token="",
        database_url="postgresql+asyncpg://u:p@127.0.0.1/db",
        database_mode="external",
        redis_url="redis://127.0.0.1:6379/0",
        config_path="",
    )


def test_resolve_ngrok_tunnel_target_skips_localhost() -> None:
    settings = _settings(control_panel_url="http://127.0.0.1:8787")
    assert ngrok.resolve_ngrok_tunnel_target(settings) is None


def test_resolve_ngrok_tunnel_target_for_ngrok_url() -> None:
    settings = _settings(
        control_panel_url="https://mistie-unmobile-reflectively.ngrok-free.dev",
        webhook_bind="127.0.0.1:8787",
    )
    target = ngrok.resolve_ngrok_tunnel_target(settings)
    assert target is not None
    assert target.public_host == "mistie-unmobile-reflectively.ngrok-free.dev"
    assert target.local_port == 8787
    assert target.domain == "mistie-unmobile-reflectively.ngrok-free.dev"


def test_resolve_ngrok_tunnel_target_uses_yaml_when_env_overrides_localhost() -> None:
    settings = _settings(
        control_panel_url="http://127.0.0.1:8787",
        yaml_control_panel_url="https://mistie-unmobile-reflectively.ngrok-free.dev",
    )
    target = ngrok.resolve_ngrok_tunnel_target(settings)
    assert target is not None
    assert target.public_host == "mistie-unmobile-reflectively.ngrok-free.dev"


def test_tunnel_matches_target_checks_host_and_port() -> None:
    target = ngrok.NgrokTunnelTarget(
        public_host="mistie-unmobile-reflectively.ngrok-free.dev",
        local_port=8787,
        domain="mistie-unmobile-reflectively.ngrok-free.dev",
    )
    tunnel = {
        "public_url": "https://mistie-unmobile-reflectively.ngrok-free.dev",
        "config": {"addr": "http://127.0.0.1:8787"},
    }
    assert ngrok.tunnel_matches_target(tunnel, target=target) is True


def test_ensure_ngrok_tunnel_skips_when_tunnel_already_active() -> None:
    settings = _settings(control_panel_url="https://example.ngrok-free.dev")
    target = ngrok.NgrokTunnelTarget(
        public_host="example.ngrok-free.dev",
        local_port=8787,
        domain="example.ngrok-free.dev",
    )
    with (
        patch.object(ngrok, "resolve_ngrok_tunnel_target", return_value=target),
        patch.object(ngrok, "has_active_tunnel", return_value=True),
        patch.object(ngrok, "start_ngrok_process") as start_mock,
    ):
        assert ngrok.ensure_ngrok_tunnel(settings) is True
    start_mock.assert_not_called()


def test_ensure_ngrok_tunnel_starts_process_when_missing() -> None:
    settings = _settings(control_panel_url="https://example.ngrok-free.dev")
    target = ngrok.NgrokTunnelTarget(
        public_host="example.ngrok-free.dev",
        local_port=8787,
        domain="example.ngrok-free.dev",
    )
    with (
        patch.object(ngrok, "resolve_ngrok_tunnel_target", return_value=target),
        patch.object(ngrok, "has_active_tunnel", side_effect=[False, True]),
        patch("control_panel.services.ngrok.shutil.which", return_value="ngrok"),
        patch.object(ngrok, "start_ngrok_process") as start_mock,
        patch.object(ngrok, "wait_for_tunnel", return_value=True),
    ):
        assert ngrok.ensure_ngrok_tunnel(settings) is True
    start_mock.assert_called_once_with(target=target)


def test_env_autostart_disabled() -> None:
    settings = _settings(control_panel_url="https://example.ngrok-free.dev")
    with patch.dict(os.environ, {"FIGMA_CP_NGROK_AUTOSTART": "0"}, clear=False):
        assert ngrok.resolve_ngrok_tunnel_target(settings) is None


@pytest.mark.parametrize(
    ("bind", "port"),
    [
        ("127.0.0.1:8787", 8787),
        ("0.0.0.0:9001", 9001),
    ],
)
def test_parse_webhook_port(bind: str, port: int) -> None:
    assert ngrok.parse_webhook_port(bind) == port
