"""Database URL resolution for bundled vs external Postgres."""

from __future__ import annotations

import pytest

from discord_bot.config.database_url import resolve_database_url
from discord_bot.config.models import DatabaseConfig, DatabaseMode
from figma_flutter_agent.errors import FigmaFlutterError


@pytest.mark.control_plane
def test_explicit_env_url_wins() -> None:
    url = resolve_database_url(
        config=DatabaseConfig(mode=DatabaseMode.BUNDLED),
        env_database_url="postgresql+asyncpg://u:p@custom:5432/db",
        env_database_mode="",
        env_pg_password="",
    )
    assert url == "postgresql+asyncpg://u:p@custom:5432/db"


@pytest.mark.control_plane
def test_bundled_builds_url_from_password() -> None:
    url = resolve_database_url(
        config=DatabaseConfig(
            mode=DatabaseMode.BUNDLED,
            bundled_host="postgres",
            user="figma_cp",
            database="figma_control_plane",
        ),
        env_database_url="",
        env_database_mode="",
        env_pg_password="secret",
    )
    assert url == "postgresql+asyncpg://figma_cp:secret@postgres:5432/figma_control_plane"


@pytest.mark.control_plane
def test_bundled_requires_password_without_env_url() -> None:
    with pytest.raises(FigmaFlutterError, match="FIGMA_CP_PG_PASSWORD"):
        resolve_database_url(
            config=DatabaseConfig(mode=DatabaseMode.BUNDLED),
            env_database_url="",
            env_database_mode="",
            env_pg_password="",
        )


@pytest.mark.control_plane
def test_external_requires_url() -> None:
    with pytest.raises(FigmaFlutterError, match="external"):
        resolve_database_url(
            config=DatabaseConfig(mode=DatabaseMode.EXTERNAL, url=""),
            env_database_url="",
            env_database_mode="",
            env_pg_password="",
        )


@pytest.mark.control_plane
def test_external_uses_yaml_url() -> None:
    url = resolve_database_url(
        config=DatabaseConfig(
            mode=DatabaseMode.EXTERNAL,
            url="postgresql+asyncpg://u:p@db.example.com:5432/figma_control_plane",
        ),
        env_database_url="",
        env_database_mode="",
        env_pg_password="",
    )
    assert "db.example.com" in url


@pytest.mark.control_plane
def test_env_mode_overrides_yaml() -> None:
    url = resolve_database_url(
        config=DatabaseConfig(
            mode=DatabaseMode.BUNDLED,
            url="postgresql+asyncpg://ignored@x/ignored",
        ),
        env_database_url="",
        env_database_mode="external",
        env_pg_password="",
    )
    assert "ignored@x" in url
