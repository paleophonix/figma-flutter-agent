"""Discord slash-command access checks."""

from __future__ import annotations

import disnake

from control_panel.config.models import AccessMode, DiscordBotYamlConfig


def is_authorized(
    inter: disnake.ApplicationCommandInteraction,
    yaml_config: DiscordBotYamlConfig,
) -> bool:
    """Return True when the invoker may run bot commands."""
    access = yaml_config.discord.access
    if access.mode == AccessMode.EVERYONE:
        return True
    user_id = inter.author.id
    if access.mode == AccessMode.ALLOWLIST:
        return user_id in access.allowed_user_ids
    if access.mode == AccessMode.ROLES:
        if user_id in access.allowed_user_ids:
            return True
        if inter.guild is None:
            return False
        member = inter.author
        if not isinstance(member, disnake.Member):
            return False
        allowed = {str(role_id) for role_id in access.allowed_role_ids}
        return any(str(role.id) in allowed for role in member.roles)
    return False
