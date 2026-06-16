"""Resolve PostgreSQL connection URLs for bundled vs external database modes."""

from __future__ import annotations

from urllib.parse import quote_plus

from figma_flutter_agent.errors import FigmaFlutterError

from .models import DatabaseConfig, DatabaseMode

DEFAULT_BUNDLED_HOST = "postgres"
DEFAULT_BUNDLED_PORT = 5432
DEFAULT_DATABASE_NAME = "figma_control_plane"
DEFAULT_DATABASE_USER = "figma_cp"


def build_bundled_database_url(
    *,
    config: DatabaseConfig,
    password: str,
) -> str:
    """Build an asyncpg SQLAlchemy URL for the bundled Postgres service."""
    if not password.strip():
        raise FigmaFlutterError(
            "FIGMA_CP_PG_PASSWORD is required when database.mode is bundled "
            "(unless FIGMA_CP_DATABASE_URL is set)."
        )
    user = quote_plus(config.user or DEFAULT_DATABASE_USER)
    secret = quote_plus(password)
    host = config.bundled_host or DEFAULT_BUNDLED_HOST
    port = config.bundled_port or DEFAULT_BUNDLED_PORT
    database = config.database or DEFAULT_DATABASE_NAME
    return f"postgresql+asyncpg://{user}:{secret}@{host}:{port}/{database}"


def resolve_database_url(
    *,
    config: DatabaseConfig,
    env_database_url: str,
    env_database_mode: str,
    env_pg_password: str,
) -> str:
    """Resolve the effective database URL from YAML and environment.

    Priority:
    1. ``FIGMA_CP_DATABASE_URL`` when set (full override).
    2. ``external`` mode → ``database.url`` from YAML.
    3. ``bundled`` mode → URL built from ``database.*`` + ``FIGMA_CP_PG_PASSWORD``.
    """
    explicit_url = env_database_url.strip()
    if explicit_url:
        return explicit_url

    mode_raw = env_database_mode.strip() or config.mode.value
    try:
        mode = DatabaseMode(mode_raw)
    except ValueError as exc:
        msg = f"Invalid database mode {mode_raw!r}; expected bundled or external."
        raise FigmaFlutterError(msg) from exc

    if mode == DatabaseMode.EXTERNAL:
        external_url = config.url.strip()
        if not external_url:
            raise FigmaFlutterError(
                "database.mode is external but no URL is configured. "
                "Set database.url in .discord-bot.yml or FIGMA_CP_DATABASE_URL in .env."
            )
        return external_url

    return build_bundled_database_url(config=config, password=env_pg_password)
