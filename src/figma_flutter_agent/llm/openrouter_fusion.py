"""OpenRouter Fusion plugin payloads for multi-model repair steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenRouterFusionInvocation:
    """Resolved OpenRouter chat request shape for one pipeline step."""

    model: str
    analysis_models: tuple[str, ...] | None
    judge_model: str | None
    use_fusion: bool

    def plugins_payload(self) -> list[dict[str, Any]] | None:
        """Build OpenRouter ``plugins`` array for Fusion, if applicable."""
        if not self.use_fusion or not self.analysis_models:
            return None
        judge = self.judge_model or self.analysis_models[0]
        return [
            {
                "id": "fusion",
                "analysis_models": list(self.analysis_models),
                "model": judge,
            }
        ]


def build_fusion_invocation(
    *,
    fusion_model: str,
    judge_model: str,
    analysis_models: tuple[str, ...],
) -> OpenRouterFusionInvocation:
    """Build a Fusion panel request (outer model + analysis_models + judge).

    Args:
        fusion_model: OpenRouter outer alias (typically ``openrouter/fusion``).
        judge_model: Judge slug inside the fusion plugin ``model`` field.
        analysis_models: Panel slugs (1–8) for parallel analysis.

    Returns:
        Invocation descriptor for the OpenRouter chat API.

    Raises:
        ValueError: When ``analysis_models`` is empty or longer than eight slugs.
    """
    if not analysis_models:
        raise ValueError("analysis_models must contain at least one model slug")
    if len(analysis_models) > 8:
        raise ValueError("OpenRouter Fusion allows at most 8 analysis_models")
    return OpenRouterFusionInvocation(
        model=fusion_model,
        analysis_models=analysis_models,
        judge_model=judge_model,
        use_fusion=True,
    )


def build_single_invocation(*, model: str) -> OpenRouterFusionInvocation:
    """Build a direct single-model OpenRouter request (no Fusion plugin)."""
    slug = model.strip()
    if not slug:
        raise ValueError("model slug must be non-empty")
    return OpenRouterFusionInvocation(
        model=slug,
        analysis_models=None,
        judge_model=None,
        use_fusion=False,
    )
