"""Path resolution utilities for agent configuration."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.errors import FigmaFlutterError


def agent_repo_root() -> Path:
    """Return the ``figma-flutter-agent`` repository root directory."""
    return Path(__file__).resolve().parents[3]


def resolve_agent_config_path(explicit: Path | None = None) -> Path:
    """Return the canonical agent YAML config path (agent repo, not the Flutter project).

    Precedence when ``explicit`` is omitted:
        ``<agent_repo>/.ai-figma-flutter.yml`` → ``<agent_repo>/.ai-figma-flutter.yml.example``

    Args:
        explicit: Optional override (for example ``--config`` on the CLI).

    Returns:
        Resolved config file path.

    Raises:
        FigmaFlutterError: When no config file exists.
    """
    if explicit is not None:
        resolved = explicit.expanduser().resolve()
        if not resolved.is_file():
            raise FigmaFlutterError(f"Config file not found: {resolved}")
        return resolved

    root = agent_repo_root()
    local = root / ".ai-figma-flutter.yml"
    if local.is_file():
        return local
    example = root / ".ai-figma-flutter.yml.example"
    if example.is_file():
        return example
    raise FigmaFlutterError(
        "Missing agent config. Copy .ai-figma-flutter.yml.example to "
        ".ai-figma-flutter.yml in the figma-flutter-agent repo root."
    )
