"""Wizard multi-model screen IR compare (write ``ir_1.json`` … ``ir_3.json``)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.paths import compare_ir_artifact_path
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.pipeline.deps import PipelineDependencies, _build_llm_client
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
)


@dataclass(frozen=True)
class LlmCompareResult:
    """Paths and metadata from a wizard compare run."""

    artifacts: tuple[Path, ...]
    models: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def write_compare_ir_artifact(
    *,
    project_dir: Path,
    feature_name: str,
    index: int,
    model: str,
    response: FlutterGenerationResponse,
) -> Path:
    """Persist one compare IR snapshot beside other per-screen debug artifacts.

    Args:
        project_dir: Flutter project root used for debug path resolution.
        feature_name: Resolved screen feature slug.
        index: Compare slot ``1``..``3``.
        model: Provider model id used for this generation.
        response: Validated LLM generation payload containing ``screenIr``.

    Returns:
        Path written under ``.debug/screen/<project>/<feature>/ir_<index>.json``.

    Raises:
        LlmError: When ``screenIr`` is missing from the response.
    """
    if response.screen_ir is None:
        raise LlmError(f"Compare model {model!r} returned no screenIr")
    payload = {
        "stage": "compare",
        "index": index,
        "model": model,
        "featureName": feature_name,
        "screenIr": response.screen_ir.model_dump(by_alias=True, exclude_none=True),
    }
    if response.extracted_widgets:
        payload["extractedWidgets"] = [
            widget.model_dump(by_alias=True, exclude_none=True)
            for widget in response.extracted_widgets
        ]
    path = compare_ir_artifact_path(project_dir, feature_name, index)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved compare IR {} ({}) to {}", index, model, path.as_posix())
    return path


async def run_llm_ir_compare(
    *,
    settings: Settings,
    project_dir: Path,
    resolved_feature: str,
    clean_tree: CleanDesignTreeNode,
    tokens: DesignTokens,
    asset_manifest: AssetManifest,
    widget_hints: list[str],
    navigation_hints: list[str],
    routing_on: bool,
    figma_reference_png: bytes | None,
    pipeline_deps: PipelineDependencies,
) -> LlmCompareResult:
    """Generate screen IR once per configured compare model.

    Args:
        settings: Active agent settings (provider, keys, compare model slots).
        project_dir: Flutter project root for validation and artifact paths.
        resolved_feature: Screen feature slug.
        clean_tree: Parsed design tree for prompts and IR validation.
        tokens: Design tokens for prompts and IR guards.
        asset_manifest: Exported asset manifest entries for the LLM user payload.
        widget_hints: Widget extraction hints for the LLM user payload.
        navigation_hints: Navigation hints for the LLM user payload.
        routing_on: Whether prototype routing rules are enabled in the system prompt.
        figma_reference_png: Optional Figma reference PNG attachment.
        pipeline_deps: Pipeline dependency container (unused; kept for symmetry).

    Returns:
        Written compare artifact paths and the model ids used.

    Raises:
        LlmError: When compare models are unset or any model call fails.
    """
    _ = pipeline_deps
    models = settings.resolved_llm_compare_models()
    asset_entries = [entry.model_dump() for entry in asset_manifest.entries]
    use_screen_ir = settings.agent.generation.use_screen_ir
    require_screen_ir = settings.agent.generation.require_screen_ir
    theme_variant = settings.agent.theme.variant
    artifacts: list[Path] = []
    warnings: list[str] = []

    for index, model in enumerate(models, start=1):
        log = logger.bind(stage="llm_compare", feature_name=resolved_feature, model=model)
        log.info("Wizard compare {}/{} using model {}", index, len(models), model)
        llm_client = _build_llm_client(
            settings,
            model=model,
            temperature=settings.resolved_llm_generate_temperature(),
        )
        response = await llm_client.generate_async(
            clean_tree,
            tokens,
            settings=settings,
            feature_name=resolved_feature,
            asset_manifest=asset_entries,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            routing_enabled=routing_on,
            theme_variant=theme_variant,
            figma_reference_png=figma_reference_png,
            use_screen_ir=use_screen_ir,
            require_screen_ir=require_screen_ir,
            project_dir=project_dir,
            persist_ir_snapshots=False,
        )
        artifacts.append(
            write_compare_ir_artifact(
                project_dir=project_dir,
                feature_name=resolved_feature,
                index=index,
                model=model,
                response=response,
            )
        )

    return LlmCompareResult(
        artifacts=tuple(artifacts),
        models=tuple(models),
        warnings=tuple(warnings),
    )
