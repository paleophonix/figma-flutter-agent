"""Shared helpers for the generation pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import FlutterProjectError, GenerationError
from figma_flutter_agent.generator.layout.common import to_snake_case

if TYPE_CHECKING:
    from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens


def validate_project_dir(project_dir: Path) -> None:
    """Ensure the target path is a Flutter project root."""
    if not (project_dir / "pubspec.yaml").is_file():
        raise FlutterProjectError(f"Flutter project not found at {project_dir}")


_FIGMA_NODE_MISSING_MARKER = "was not found in Figma file"


def is_figma_node_missing_error(exc: BaseException) -> bool:
    """Return True when a live Figma fetch failed because the node id is absent."""
    return isinstance(exc, FlutterProjectError) and _FIGMA_NODE_MISSING_MARKER in str(exc)


def resolve_manifest_cached_dump(
    project_dir: Path,
    *,
    feature_name: str | None = None,
    node_id: str | None = None,
    file_key: str | None = None,
) -> Path | None:
    """Return an on-disk ``screens.yaml`` dump path when one is available.

    Args:
        project_dir: Flutter project root (contains ``screens.yaml``).
        feature_name: Optional manifest feature slug.
        node_id: Optional Figma node id (``page:frame``) to match one screen.
        file_key: When set, ignore the manifest when its ``file_key`` differs.

    Returns:
        Resolved dump path, or ``None`` when no manifest or no matching dump file.
    """
    from figma_flutter_agent.batch.manifest import find_screen_entry, load_batch_manifest
    from figma_flutter_agent.batch.run import _resolve_dump

    manifest_path = project_dir.expanduser().resolve() / "screens.yaml"
    if not manifest_path.is_file():
        return None
    try:
        manifest = load_batch_manifest(manifest_path)
    except (OSError, ValueError):
        return None
    if file_key is not None and manifest.file_key != file_key:
        return None

    screens = list(manifest.screens)
    if feature_name:
        try:
            screens = [find_screen_entry(manifest, feature_name)]
        except ValueError:
            return None
    elif node_id:
        normalized = node_id.replace("-", ":")
        matched = [screen for screen in manifest.screens if screen.node_id == normalized]
        if len(matched) == 1:
            screens = matched

    for screen in screens:
        dump_path = _resolve_dump(screen, manifest.project_dir)
        if dump_path.is_file():
            return dump_path
    return None


def validate_runtime_credentials(
    settings: Settings,
    *,
    dry_run: bool,
    require_figma_token: bool = True,
    require_llm_api_key: bool | None = None,
) -> None:
    """Validate tokens required for the configured generation mode."""
    if require_figma_token and not settings.figma_token():
        raise FlutterProjectError("FIGMA_ACCESS_TOKEN is required")
    needs_llm_key = True if require_llm_api_key is None else require_llm_api_key
    if not dry_run and needs_llm_key and not settings.llm_api_key():
        raise FlutterProjectError(
            f"{settings.llm_api_key_env_name()} is required for LLM provider "
            f"'{settings.resolved_llm_provider()}'"
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
    pipeline_run_id: str | None = None,
) -> Path | None:
    """Write a planned Dart debug bundle under ``.debug/dart`` or ``dart.bug``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug.
        planned_files: Planned paths to Dart sources.
        package_name: Target app package name from ``pubspec.yaml``.
        architecture: ``feature_first`` or ``layer_first``.
        snapshot: ``plan``, ``final``, or ``bug``.
        pipeline_run_id: Optional run id for ``FFA_RUN_ID`` stamp.

    Returns:
        Written path, or ``None`` when the screen file is absent from ``planned_files``.
    """
    from figma_flutter_agent.debug.dart_bundle import write_dart_debug_snapshot

    return write_dart_debug_snapshot(
        project_dir,
        feature_name=feature_name,
        planned_files=planned_files,
        package_name=package_name,
        architecture=architecture,  # type: ignore[arg-type]
        snapshot=snapshot,  # type: ignore[arg-type]
        pipeline_run_id=pipeline_run_id,
    )


def enforce_emit_parse_gate(
    settings: Settings,
    planned_files: dict[str, str],
    *,
    package_name: str,
    stage: str,
    typography_tokens: DesignTokens | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
    feature_name: str | None = None,
    screen_class: str | None = None,
    routing_on: bool = False,
    on_parse_gate_failure: Callable[[dict[str, str]], None] | None = None,
) -> None:
    """Fail-fast when emitter output is not dart-format-parseable (temp tree only)."""
    if not settings.agent.validation.emit_parse_gate or not planned_files:
        return
    from figma_flutter_agent.generator.dart.project_validation import gate_planned_dart_syntax
    from figma_flutter_agent.generator.planned.reconcile.bootstrap_refresh import (
        build_planned_bootstrap_context,
    )

    bootstrap_context = None
    if feature_name is not None:
        bootstrap_context = build_planned_bootstrap_context(
            settings=settings,
            package_name=package_name,
            feature_name=feature_name,
            screen_class=screen_class,
            app_title=clean_tree.name if clean_tree is not None else None,
            routing_on=routing_on,
        )

    outcome = gate_planned_dart_syntax(
        planned_files,
        package_name=package_name,
        require_dart_sdk=settings.agent.validation.require_dart_sdk,
        flutter_sdk=settings.flutter_sdk or None,
        analyze_stage=stage,
        typography_tokens=typography_tokens,
        clean_tree=clean_tree,
        bootstrap_context=bootstrap_context,
    )
    if outcome.skipped or outcome.passed:
        return
    if on_parse_gate_failure is not None:
        on_parse_gate_failure(planned_files)
    preview = "; ".join(outcome.errors[:5])
    raise GenerationError(
        f"Refusing to continue: planned Dart failed emit parse gate ({outcome.detail}): {preview}"
    )
