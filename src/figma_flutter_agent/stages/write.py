"""Write stage for committing generated Dart files to disk."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen import run_build_runner, run_pub_get
from figma_flutter_agent.generator.pub_get_policy import pubspec_digest
from figma_flutter_agent.generator.pubspec import (
    PubspecUpdateBatch,
    commit_pubspec_batch,
    rollback_pubspec_batch,
    update_pubspec,
)
from figma_flutter_agent.generator.validation import validate_dart_project
from figma_flutter_agent.generator.writer import DartWriter, WriteBatch
from figma_flutter_agent.schemas import AssetManifest, FontManifest


@dataclass
class WriteStageRequest:
    """Inputs required to write generated files and update pubspec."""

    project_dir: Path
    files_to_write: dict[str, str]
    asset_manifest: AssetManifest
    routing_type: str
    state_management_type: str
    package_name: str = "demo_app"
    emit_parse_gate: bool = False
    font_manifest: FontManifest = field(default_factory=FontManifest)
    enable_backup: bool = True
    require_dart_sdk: bool = False
    flutter_sdk: str | None = None
    strict_preservation: bool = False
    analyze_scope: str = "generated_only"
    analyze_relative_paths: list[str] | None = None
    planned_files_for_widget_cleanup: dict[str, str] | None = None
    dart_writer_factory: Callable[..., DartWriter] | None = None


@dataclass
class WriteStageResult:
    """Output of a successful write stage."""

    written_files: list[str]


def commit_planned_files(request: WriteStageRequest) -> WriteStageResult:
    """Write generated Dart files, update pubspec, and validate the project.

    Args:
        request: Write-stage inputs including files and routing configuration.

    Returns:
        Relative paths of files written to the Flutter project.

    Raises:
        GenerationError: When Dart validation fails after generation.
        OSError: When file writes fail.
    """
    if not request.files_to_write:
        logger.info("Write stage skipped: no files required updates")
        return WriteStageResult(written_files=[])

    from figma_flutter_agent.generator.planned_dart import prepare_files_for_write_commit

    files_to_write = prepare_files_for_write_commit(
        request.files_to_write,
        request.planned_files_for_widget_cleanup,
    )

    if request.emit_parse_gate:
        from figma_flutter_agent.generator.validation import gate_planned_dart_syntax

        gate = gate_planned_dart_syntax(
            files_to_write,
            package_name=request.package_name,
            require_dart_sdk=request.require_dart_sdk,
            flutter_sdk=request.flutter_sdk,
            analyze_stage="write_parse_gate",
        )
        if not gate.skipped and not gate.passed:
            preview = "; ".join(gate.errors[:5])
            raise GenerationError(
                "Write stage blocked by emit parse gate "
                f"({gate.detail}): {preview}"
            )

    writer_factory = request.dart_writer_factory
    if writer_factory is None:
        writer = DartWriter(
            request.project_dir,
            enable_backup=request.enable_backup,
            strict_preservation=request.strict_preservation,
        )
    else:
        writer = writer_factory(
            request.project_dir,
            enable_backup=request.enable_backup,
            strict_preservation=request.strict_preservation,
        )
    uses_svg = any(item.kind == "icon" for item in request.asset_manifest.entries)
    write_batch: WriteBatch | None = None
    pubspec_batch: PubspecUpdateBatch | None = None
    try:
        from figma_flutter_agent.generator.planned_dart import prune_disk_widget_stem_aliases

        cleanup_planned = request.planned_files_for_widget_cleanup or files_to_write
        prune_disk_widget_stem_aliases(request.project_dir, cleanup_planned)
        write_batch = writer.write_files(files_to_write)
        has_illustrations = any(
            entry.kind == "illustration" for entry in request.asset_manifest.entries
        )
        asset_dirs = ["assets/icons/", "assets/images/"]
        if has_illustrations:
            asset_dirs.append("assets/illustrations/")
        # Font files belong in flutter.fonts only — listing assets/fonts/ in flutter.assets
        # breaks web font loading (assets/assets/fonts/...).
        pubspec_before = pubspec_digest(request.project_dir)
        pubspec_batch = update_pubspec(
            request.project_dir,
            asset_dirs,
            needs_svg=uses_svg,
            needs_go_router=request.routing_type == "go_router",
            needs_auto_route=request.routing_type == "auto_route",
            state_management_type=request.state_management_type,
            font_manifest=request.font_manifest,
        )
        pubspec_after = pubspec_digest(request.project_dir)
        pubspec_changed = pubspec_before != pubspec_after
        if request.routing_type == "auto_route":
            sdk_required = request.require_dart_sdk
            run_pub_get(
                request.project_dir,
                require_dart_sdk=sdk_required,
                pubspec_changed=pubspec_changed,
            )
            run_build_runner(request.project_dir, require_dart_sdk=sdk_required)
        if request.analyze_scope == "written_only":
            analyze_paths = sorted(files_to_write.keys())
            analyze_scope = "written_only"
        elif request.analyze_scope == "all_planned":
            analyze_paths = sorted(request.analyze_relative_paths or files_to_write.keys())
            analyze_scope = "all_planned"
        else:
            analyze_paths = sorted(request.analyze_relative_paths or files_to_write.keys())
            analyze_scope = request.analyze_scope
        validate_dart_project(
            request.project_dir,
            require_dart_sdk=request.require_dart_sdk,
            analyze_scope=analyze_scope,
            relative_paths=analyze_paths,
            flutter_sdk=request.flutter_sdk,
        )
    except (GenerationError, OSError, RuntimeError):
        logger.exception("Write stage failed; rolling back staged files")
        writer.rollback_batch(write_batch)
        rollback_pubspec_batch(pubspec_batch)
        raise

    writer.commit_batch(write_batch)
    commit_pubspec_batch(pubspec_batch)
    written = sorted(files_to_write.keys())
    logger.info("Write stage complete with {} files", len(written))
    return WriteStageResult(written_files=written)
