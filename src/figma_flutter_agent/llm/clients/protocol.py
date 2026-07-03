"""LlmClient Protocol and small shared helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from figma_flutter_agent.config import Settings

from figma_flutter_agent.llm.refine_context import RefineAttemptSummary, RefineFocus
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
)
from figma_flutter_agent.validation.pixel.models import DiffBandRegion

_PROVIDER_API_LABELS: dict[str, str] = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "google": "Google AI Studio",
}


def _provider_api_label(provider: str) -> str:
    """Return a user-facing provider name for API error messages."""
    return _PROVIDER_API_LABELS.get(provider, provider)


def _describe_empty_chat_completion(response: object) -> str:
    """Summarize an OpenAI-compat completion object that has no ``choices``."""
    parts: list[str] = []
    response_id = getattr(response, "id", None)
    if response_id:
        parts.append(f"id={response_id!r}")
    response_model = getattr(response, "model", None)
    if response_model:
        parts.append(f"response_model={response_model!r}")
    error = getattr(response, "error", None)
    if error is not None:
        parts.append(f"error={error!r}")
    return "; ".join(parts) if parts else "empty chat completion payload"


def _first_chat_choice(
    response: object,
    *,
    provider: str,
    model: str,
) -> object:
    """Return the first chat completion choice or raise ``LlmError``."""
    from loguru import logger

    from figma_flutter_agent.errors import LlmError

    choices = getattr(response, "choices", None)
    if not choices:
        detail = _describe_empty_chat_completion(response)
        logger.warning(
            "{} returned no completion choices (model={}): {}",
            _provider_api_label(provider),
            model,
            detail,
        )
        raise LlmError(
            f"{_provider_api_label(provider)} returned no completion choices "
            f"(model={model}): {detail}",
        )
    return choices[0]


class LlmClient(Protocol):
    """Protocol for structured Flutter codegen clients."""

    def generate(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        settings: Settings,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
    ) -> FlutterGenerationResponse:
        """Generate structured Flutter code from design artifacts."""

    async def generate_async(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        settings: Settings,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
    ) -> FlutterGenerationResponse:
        """Generate structured Flutter code without blocking the event loop on retry backoff."""

    async def repair_async(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        current_generation: FlutterGenerationResponse,
        analyze_errors: list[str],
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        planned_files: dict[str, str] | None = None,
        architecture: str = "feature_first",
        use_screen_ir: bool = False,
        project_dir: Path | None = None,
    ) -> FlutterGenerationResponse:
        """Repair structured Flutter code after analyze failures."""

    async def visual_refine_async(
        self,
        clean_tree: CleanDesignTreeNode,
        tokens: DesignTokens,
        *,
        settings: Settings,
        feature_name: str,
        asset_manifest: list[dict[str, str]],
        current_generation: FlutterGenerationResponse,
        changed_ratio: float,
        threshold: float,
        widget_hints: list[str] | None = None,
        navigation_hints: list[str] | None = None,
        routing_enabled: bool = False,
        theme_variant: str = "material_3",
        figma_reference_png: bytes | None = None,
        flutter_render_png: bytes | None = None,
        visual_diff_png: bytes | None = None,
        refine_attempt: int = 1,
        max_refine_attempts: int = 1,
        previous_changed_ratio: float | None = None,
        refine_focus: RefineFocus = "interaction",
        diff_bands: tuple[DiffBandRegion, ...] = (),
        refine_history: tuple[RefineAttemptSummary, ...] = (),
        interactive_inventory: list[dict[str, Any]] | None = None,
        handler_audit: dict[str, Any] | None = None,
        canvas_size: dict[str, float | int] | None = None,
        asset_warnings: list[str] | None = None,
        use_screen_ir: bool = False,
        require_screen_ir: bool = False,
        project_dir: Path | None = None,
    ) -> FlutterGenerationResponse:
        """Refine structured Flutter code using Figma, render, and diff heatmap PNGs."""
