"""Write stage for committing generated Dart files to disk."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen import run_build_runner, run_pub_get
from figma_flutter_agent.generator.dart.project_validation import analyze_planned_dart_files
from figma_flutter_agent.generator.pub_get_policy import pubspec_digest
from figma_flutter_agent.generator.pubspec import (
    PubspecUpdateBatch,
    commit_pubspec_batch,
    rollback_pubspec_batch,
    update_pubspec,
)
from figma_flutter_agent.generator.writing.core import DartWriter
from figma_flutter_agent.generator.writing.models import WriteBatch
from figma_flutter_agent.schemas import AssetManifest, FontManifest

if TYPE_CHECKING:
    from figma_flutter_agent.generator.planned.graph import PlannedDartGraph
    from figma_flutter_agent.generator.planned.reconcile.bootstrap_refresh import (
        PlannedBootstrapContext,
    )


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
    frozen_planned_graph: PlannedDartGraph | None = None
    dart_writer_factory: Callable[..., DartWriter] | None = None
    feature_name: str | None = None
    architecture: str = "feature_first"
    bootstrap_context: PlannedBootstrapContext | None = None
    on_parse_gate_failure: Callable[[dict[str, str]], None] | None = None


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

    from figma_flutter_agent.generator.planned.graph import (
        PlannedDartGraph,
        project_write_payload,
    )

    if request.frozen_planned_graph is not None:
        frozen = request.frozen_planned_graph
        if not isinstance(frozen, PlannedDartGraph):
            msg = "frozen_planned_graph must be a PlannedDartGraph instance"
            raise TypeError(msg)
        files_to_write = project_write_payload(frozen, request.files_to_write)
    else:
        from figma_flutter_agent.generator.planned.reconcile import prepare_files_for_write_commit

        files_to_write = prepare_files_for_write_commit(
            request.files_to_write,
            request.planned_files_for_widget_cleanup,
            package_name=request.package_name,
            project_dir=request.project_dir,
        )

    if request.emit_parse_gate:
        from figma_flutter_agent.generator.dart.project_validation import gate_planned_dart_syntax

        gate = gate_planned_dart_syntax(
            files_to_write,
            package_name=request.package_name,
            require_dart_sdk=request.require_dart_sdk,
            flutter_sdk=request.flutter_sdk,
            analyze_stage="write_parse_gate",
            bootstrap_context=request.bootstrap_context,
        )
        if not gate.skipped and not gate.passed:
            if request.on_parse_gate_failure is not None:
                request.on_parse_gate_failure(files_to_write)
            elif request.feature_name is not None:
                from figma_flutter_agent.pipeline.helpers import (
                    persist_planned_dart_debug_snapshot,
                )

                persist_planned_dart_debug_snapshot(
                    request.project_dir,
                    feature_name=request.feature_name,
                    planned_files=files_to_write,
                    package_name=request.package_name,
                    architecture=request.architecture,
                    snapshot="bug",
                )
            preview = "; ".join(gate.errors[:5])
            raise GenerationError(
                f"Write stage blocked by emit parse gate ({gate.detail}): {preview}"
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
    uses_svg = any(
        item.asset_path.lower().endswith(".svg") for item in request.asset_manifest.entries
    )
    write_batch: WriteBatch | None = None
    pubspec_batch: PubspecUpdateBatch | None = None
    try:
        from figma_flutter_agent.generator.planned.reconcile import prune_disk_widget_stem_aliases

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
        from figma_flutter_agent.generator.dart.project_validation.write_analyze import (
            resolve_planned_for_write_analyze,
        )

        planned_for_analyze = resolve_planned_for_write_analyze(
            analyze_paths,
            files_to_write=files_to_write,
            planned_catalog=request.planned_files_for_widget_cleanup,
            project_dir=request.project_dir,
            package_name=request.package_name,
        )
        analyze_outcome = analyze_planned_dart_files(
            planned_for_analyze,
            package_name=request.package_name,
            require_dart_sdk=request.require_dart_sdk,
            analyze_scope=analyze_scope,
            analyze_stage="write",
            flutter_sdk=request.flutter_sdk,
            skip_planned_reconcile=True,
            validate_graph_only=True,
        )
        if not analyze_outcome.skipped and not analyze_outcome.passed:
            raise GenerationError(analyze_outcome.detail)
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
