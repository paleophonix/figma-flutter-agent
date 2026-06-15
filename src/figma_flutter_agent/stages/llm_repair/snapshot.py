"""Generation snapshot management for LLM repair loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from figma_flutter_agent.schemas import (
    FlutterGenerationResponse,
    ScreenIr,
    WidgetIrNode,
)

if TYPE_CHECKING:
    pass

_EXTRACTED_WIDGET_DRIFT_MARKERS = (
    "isn't a class",
    "creation_with_non_type",
    "undefined_method",
)


@dataclass(frozen=True)
class _GenerationSnapshot:
    screen_code: str
    screen_ir_fingerprint: str | None
    widget_codes: tuple[tuple[str, str], ...]
    widget_ir_fingerprints: tuple[tuple[str, str | None], ...]


def _widget_ir_fingerprint(widget_ir: WidgetIrNode | None) -> str | None:
    if widget_ir is None:
        return None
    return widget_ir.model_dump_json(by_alias=True)


def _screen_ir_fingerprint(screen_ir: ScreenIr | None) -> str | None:
    if screen_ir is None:
        return None
    return screen_ir.model_dump_json(by_alias=True)


def _snapshot_generation(
    generation: FlutterGenerationResponse,
) -> _GenerationSnapshot:
    return _GenerationSnapshot(
        screen_code=generation.screen_code,
        screen_ir_fingerprint=_screen_ir_fingerprint(generation.screen_ir),
        widget_codes=tuple(
            (widget.widget_name, widget.resolved_code()) for widget in generation.extracted_widgets
        ),
        widget_ir_fingerprints=tuple(
            (widget.widget_name, _widget_ir_fingerprint(widget.widget_ir))
            for widget in generation.extracted_widgets
        ),
    )


def _restore_generation(
    generation: FlutterGenerationResponse,
    snapshot: _GenerationSnapshot,
) -> None:
    generation.screen_code = snapshot.screen_code
    if snapshot.screen_ir_fingerprint is not None:
        generation.screen_ir = ScreenIr.model_validate_json(snapshot.screen_ir_fingerprint)
    by_name = {name: code for name, code in snapshot.widget_codes}
    ir_by_name = dict(snapshot.widget_ir_fingerprints)
    for widget in generation.extracted_widgets:
        if widget.widget_name in by_name:
            widget.code = by_name[widget.widget_name]
        fingerprint = ir_by_name.get(widget.widget_name)
        if fingerprint is not None:
            widget.widget_ir = WidgetIrNode.model_validate_json(fingerprint)


def _repair_generation_unchanged(
    before: _GenerationSnapshot,
    after: FlutterGenerationResponse,
    *,
    use_screen_ir: bool,
) -> bool:
    after_snapshot = _snapshot_generation(after)
    if use_screen_ir and (
        before.screen_ir_fingerprint is not None or after_snapshot.screen_ir_fingerprint is not None
    ):
        return (
            before.screen_ir_fingerprint == after_snapshot.screen_ir_fingerprint
            and before.widget_ir_fingerprints == after_snapshot.widget_ir_fingerprints
        )
    return (
        before.screen_code == after_snapshot.screen_code
        and before.widget_codes == after_snapshot.widget_codes
    )


def _errors_suggest_extracted_widget_drift(errors: tuple[str, ...]) -> bool:
    joined = " ".join(errors).lower()
    return any(marker in joined for marker in _EXTRACTED_WIDGET_DRIFT_MARKERS) and "_" in joined


def _apply_extracted_widget_reference_fixup(
    request: Any,
    result: Any,
    *,
    log: Any,
) -> bool:
    """Reconcile private widget usages in screenCode without another LLM call."""
    from figma_flutter_agent.generator.dart.llm_codegen import (
        reconcile_extracted_widget_references,
        reconcile_extracted_widget_references_in_planned,
    )
    from figma_flutter_agent.generator.planned.reconcile import reconcile_planned_dart_files
    from figma_flutter_agent.stages.llm_repair.replan import replan_planned_files

    generation = result.llm_result.generation
    if generation is None or not generation.extracted_widgets:
        return False
    pairs = [
        (widget.widget_name, widget.resolved_code())
        for widget in generation.extracted_widgets
        if widget.resolved_code()
    ]
    if generation.screen_code:
        reconciled = reconcile_extracted_widget_references(generation.screen_code, pairs)
        if reconciled == generation.screen_code:
            return False
        generation.screen_code = reconciled
        result.planned_files = replan_planned_files(
            request,
            generation,
            base_planned=result.planned_files,
        )
    else:
        updated = reconcile_extracted_widget_references_in_planned(
            result.planned_files,
            pairs,
        )
        if updated == result.planned_files:
            return False
        result.planned_files = updated
    gen_cfg = request.settings.agent.generation
    result.planned_files = reconcile_planned_dart_files(
        result.planned_files,
        blocked_asset_paths=request.blocked_asset_paths,
        typography_tokens=request.tokens,
        package_name=request.package_name,
        clean_tree=request.clean_tree,
        incremental=True,
        project_dir=request.project_dir,
        widget_suffix=request.settings.agent.naming.widget_suffix,
        uses_svg=any(item.kind == "icon" for item in request.asset_manifest.entries),
        use_package_imports=gen_cfg.use_package_imports,
        cluster_summary=request.cluster_summary,
        cluster_min_count=gen_cfg.cluster_min_count,
        destination_trees=request.destination_trees,
    )
    log.info("Reconciled extracted widget references in screenCode (deterministic)")
    return True
