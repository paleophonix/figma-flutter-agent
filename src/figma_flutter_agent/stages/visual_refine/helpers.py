"""Guard predicates and utility helpers for the visual refine stage."""

from __future__ import annotations

from figma_flutter_agent.stages.llm_repair import LlmRepairStageRequest
from figma_flutter_agent.validation.compare import compare_png_bytes
from figma_flutter_agent.validation.pixel.coordinates import parse_flutter_mapper_payload
from figma_flutter_agent.validation.pixel.models import (
    TextCoordinateValidationResult,
    VisualCompareResult,
)
from figma_flutter_agent.validation.reference import resolve_reference_png_path


def _should_run_visual_refine(request: LlmRepairStageRequest) -> bool:
    generation_cfg = request.settings.agent.generation
    if request.dry_run:
        return False
    if not generation_cfg.llm_visual_refine:
        return False
    if request.llm_result.generation is None:
        return False
    return not request.llm_result.skipped_incremental


def _resolve_figma_reference_png(request: LlmRepairStageRequest) -> bytes | None:
    if request.figma_reference_png is not None:
        return request.figma_reference_png
    reference_png = resolve_reference_png_path(
        request.project_dir,
        request.resolved_feature,
    )
    if reference_png is not None:
        return reference_png.read_bytes()
    return None


def _compare_visual(
    request: LlmRepairStageRequest,
    *,
    figma_png: bytes,
    flutter_png: bytes,
    threshold: float,
    flutter_mapper_payload: dict | None,
) -> VisualCompareResult:
    generation_cfg = request.settings.agent.generation
    outcome = compare_png_bytes(
        figma_png,
        flutter_png,
        threshold=threshold,
        clean_tree=request.clean_tree,
        flutter_mapper=parse_flutter_mapper_payload(flutter_mapper_payload),
        text_coordinate_tolerance=generation_cfg.text_coordinate_tolerance,
    )
    if isinstance(outcome, VisualCompareResult):
        return outcome
    return VisualCompareResult(
        pixel=outcome,
        text_validation=TextCoordinateValidationResult(passed=True),
    )
