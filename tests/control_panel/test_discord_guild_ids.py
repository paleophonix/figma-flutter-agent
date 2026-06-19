"""Discord guild id config tests."""

from __future__ import annotations

from control_panel.config.load import _merge_discord_env, _parse_discord_guild_ids
from control_panel.config.models import DiscordBotYamlConfig


def test_parse_discord_guild_ids() -> None:
    assert _parse_discord_guild_ids("123, 456") == (123, 456)


def test_merge_discord_env_overrides_yaml() -> None:
    yaml_config = DiscordBotYamlConfig.model_validate({"discord": {"guild_ids": [1]}})

    class Env:
        figma_cp_discord_guild_ids = "42,43"

    merged = _merge_discord_env(yaml_config, Env())
    assert merged.discord.guild_ids == [42, 43]
