"""Shared helpers for the generation pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import FlutterProjectError, GenerationError
from figma_flutter_agent.generator.layout_common import to_snake_case

if TYPE_CHECKING:
    from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens


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


def persist_planned_dart_debug_snapshot(
    project_dir: Path,
    *,
    feature_name: str,
    planned_files: dict[str, str],
    package_name: str,
    architecture: str = "feature_first",
    snapshot: str = "final",
) -> Path | None:
    """Write a planned Dart debug bundle under ``.figma_debug/dart`` or ``dart.bug``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug.
        planned_files: Planned paths to Dart sources.
        package_name: Target app package name from ``pubspec.yaml``.
        architecture: ``feature_first`` or ``layer_first``.
        snapshot: ``plan``, ``final``, or ``bug``.

    Returns:
        Written path, or ``None`` when the screen file is absent from ``planned_files``.
    """
    from figma_flutter_agent.debug.dart_bundle import write_dart_debug_snapshot
    from figma_flutter_agent.generator.paths import Architecture

    return write_dart_debug_snapshot(
        project_dir,
        feature_name=feature_name,
        planned_files=planned_files,
        package_name=package_name,
        architecture=architecture,  # type: ignore[arg-type]
        snapshot=snapshot,  # type: ignore[arg-type]
    )


def enforce_emit_parse_gate(
    settings: Settings,
    planned_files: dict[str, str],
    *,
    package_name: str,
    stage: str,
    typography_tokens: DesignTokens | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
    on_parse_gate_failure: Callable[[dict[str, str]], None] | None = None,
) -> None:
    """Fail-fast when emitter output is not dart-format-parseable (temp tree only)."""
    if not settings.agent.validation.emit_parse_gate or not planned_files:
        return
    from figma_flutter_agent.generator.validation import gate_planned_dart_syntax

    outcome = gate_planned_dart_syntax(
        planned_files,
        package_name=package_name,
        require_dart_sdk=settings.agent.validation.require_dart_sdk,
        flutter_sdk=settings.flutter_sdk or None,
        analyze_stage=stage,
        typography_tokens=typography_tokens,
        clean_tree=clean_tree,
    )
    if outcome.skipped or outcome.passed:
        return
    if on_parse_gate_failure is not None:
        on_parse_gate_failure(planned_files)
    preview = "; ".join(outcome.errors[:5])
    raise GenerationError(
        "Refusing to continue: planned Dart failed emit parse gate "
        f"({outcome.detail}): {preview}"
    )
