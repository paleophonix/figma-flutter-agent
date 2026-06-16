"""Feedback issue LLM review generation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from loguru import logger

from discord_bot.db import QUALITY_LABELS, Quality
from discord_bot.runner.review import FeedbackReview, generate_feedback_review
from figma_flutter_agent.config import load_settings
from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.clients import create_llm_client
from figma_flutter_agent.llm.clients.client import BaseLlmClient
from figma_flutter_agent.llm.schema import StructuredOutputSpec


def _feedback_output_spec(*, strict: bool) -> StructuredOutputSpec:
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["title", "body"],
        "additionalProperties": False,
    }
    return StructuredOutputSpec(
        name="feedback_review",
        schema=schema,
        anthropic_tool_name="feedback_review",
        anthropic_tool_description="Russian feedback issue title and body for a layout job.",
    )


def _read_debug_snippet(project_dir: Path, feature_slug: str, name: str, limit: int = 4000) -> str:
    root = screen_root(project_dir, feature_slug)
    path = root / name
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:limit]


def _build_llm_client():
    config_path = agent_repo_root() / ".ai-figma-flutter.yml"
    if not config_path.is_file():
        return None
    settings = load_settings(config_path)
    api_key = settings.llm_api_key()
    if not api_key:
        return None
    return create_llm_client(
        provider=settings.resolved_llm_provider(),
        api_key=api_key,
        model=settings.resolved_llm_generate_model(),
        require_strict_json_schema=settings.llm_require_strict_json_schema,
        temperature=settings.resolved_llm_generate_temperature(),
        top_p=settings.llm_top_p,
        reasoning=settings.resolved_llm_reasoning(),
        max_retries=settings.llm_max_retries,
        max_output_tokens=settings.llm_max_output_tokens,
    )


async def generate_feedback_issue_review(
    *,
    job_id: str,
    figma_url: str,
    quality: Quality,
    feature_slug: str | None,
    user_comment: str,
    project_dir: Path,
    warnings: list[str] | None = None,
) -> FeedbackReview:
    """Generate Russian issue title/body using LLM and debug artifacts."""
    slug = feature_slug or "screen"
    debug_context = {
        "lastLog": _read_debug_snippet(project_dir, slug, "last.log"),
        "dartErrors": _read_debug_snippet(project_dir, slug, "dart-errors.json"),
        "semantics": _read_debug_snippet(project_dir, slug, "semantics.json"),
        "warnings": (warnings or [])[:30],
        "userComment": user_comment,
        "qualityLabel": QUALITY_LABELS[quality],
        "featureSlug": slug,
        "figmaUrl": figma_url,
        "jobId": job_id,
    }
    client = _build_llm_client()
    if client is None:
        return await generate_feedback_review(
            job_id=job_id,
            figma_url=figma_url,
            quality_label=QUALITY_LABELS[quality],
            warnings=warnings or [],
            feature_slug=feature_slug,
        )

    system_prompt = (
        "Ты оформляешь тикет обратной связи по генерации Flutter UI из Figma. "
        "Пиши по-русски. title — краткий (до 120 символов), body — структурированный markdown "
        "с разделами: суть проблемы, что ожидал пользователь, технические наблюдения из логов."
    )
    user_payload = json.dumps(debug_context, ensure_ascii=False, indent=2)
    spec = _feedback_output_spec(strict=getattr(client, "_strict_json_schema", True))

    def _run() -> FeedbackReview:
        base = client
        if not isinstance(base, BaseLlmClient):
            raise LlmError("LLM client does not support structured feedback review")
        raw = base._request_generation(
            user_payload,
            system_prompt=system_prompt,
            figma_reference_png=None,
            output_spec=spec,
            analytics_span_name="feedback_issue_review",
        )
        parsed = json.loads(raw)
        return FeedbackReview.model_validate(parsed)

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.warning("LLM feedback review failed, using template fallback: {}", exc)
        return await generate_feedback_review(
            job_id=job_id,
            figma_url=figma_url,
            quality_label=QUALITY_LABELS[quality],
            warnings=warnings or [],
            feature_slug=feature_slug,
        )
