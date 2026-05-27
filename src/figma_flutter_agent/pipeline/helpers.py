"""Shared helpers for the generation pipeline."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.generator.layout_common import to_snake_case


def validate_project_dir(project_dir: Path) -> None:
    """Ensure the target path is a Flutter project root."""
    if not (project_dir / "pubspec.yaml").is_file():
        raise FlutterProjectError(f"Flutter project not found at {project_dir}")


def validate_runtime_credentials(
    settings: Settings,
    *,
    dry_run: bool,
    require_figma_token: bool = True,
) -> None:
    """Validate tokens required for the configured generation mode."""
    if require_figma_token and not settings.figma_token():
        raise FlutterProjectError("FIGMA_ACCESS_TOKEN is required")
    if (
        not dry_run
        and not settings.llm_api_key()
        and not settings.agent.generation.use_deterministic_screen
    ):
        raise FlutterProjectError(
            f"{settings.llm_api_key_env_name()} is required for LLM provider "
            f"'{settings.resolved_llm_provider()}' unless deterministic generation is enabled"
        )


def resolve_feature_name(frame_name: str, configured: str) -> str:
    """Resolve the feature folder name from frame metadata or config."""
    if configured != "auto":
        return to_snake_case(configured)
    return to_snake_case(frame_name)


def routing_enabled(settings: Settings) -> bool:
    """Return whether navigation codegen is enabled."""
    return settings.agent.routing.is_enabled()
