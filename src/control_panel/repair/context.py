"""Context-stage RepairTicket synthesis via LLM."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from loguru import logger

from control_panel.config import DiscordBotSettings
from control_panel.repair.snapshot import read_debug_text
from control_panel.repair.ticket import RepairTicket, repair_ticket_output_spec
from figma_flutter_agent.config import load_settings
from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.clients import create_llm_client
from figma_flutter_agent.llm.clients.client import BaseLlmClient


def _resolve_context_model(settings: DiscordBotSettings) -> str:
    model = settings.yaml.repair.models.context.strip()
    if model:
        return model
    config_path = agent_repo_root() / ".ai-figma-flutter.yml"
    if config_path.is_file():
        agent_settings = load_settings(config_path)
        return agent_settings.resolved_llm_generate_model()
    return ""


def _build_context_prompt(
    *,
    debug_root: Path,
    issue_excerpt: str,
    visual_hints: list[str],
) -> str:
    processed = read_debug_text(debug_root, "processed.json", limit=8000)
    pre_emit = read_debug_text(debug_root, "pre_emit.json", limit=6000)
    dart_errors = read_debug_text(debug_root, "dart-errors.json", limit=4000)
    last_log = read_debug_text(debug_root, "last.log", limit=4000)
    semantics = read_debug_text(debug_root, "semantics.json", limit=2000)
    parts = [
        "Synthesize a RepairTicket JSON for a figma-flutter-agent compiler failure.",
        "Use processed artifacts only; do not invent figma node ids.",
        f"Issue context:\n{issue_excerpt[:2000]}",
    ]
    if visual_hints:
        parts.append("Visual hints:\n" + "\n".join(f"- {h}" for h in visual_hints))
    if processed:
        parts.append(f"processed.json excerpt:\n{processed}")
    if pre_emit:
        parts.append(f"pre_emit.json excerpt:\n{pre_emit}")
    if dart_errors:
        parts.append(f"dart-errors.json:\n{dart_errors}")
    if last_log:
        parts.append(f"last.log tail:\n{last_log}")
    if semantics:
        parts.append(f"semantics.json excerpt:\n{semantics}")
    return "\n\n".join(parts)


async def synthesize_repair_ticket(
    *,
    settings: DiscordBotSettings,
    debug_root: Path,
    issue_excerpt: str = "",
    visual_hints: list[str] | None = None,
) -> RepairTicket:
    """Run context model to produce a structured RepairTicket.

    Args:
        settings: Control panel settings with repair model slots.
        debug_root: Copied processed debug bundle in the worktree.
        issue_excerpt: GitLab issue title/body excerpt.
        visual_hints: Optional recognition-stage hints.

    Returns:
        Parsed RepairTicket.

    Raises:
        LlmError: When the LLM call or JSON parse fails.
    """
    hints = visual_hints or []
    prompt = _build_context_prompt(
        debug_root=debug_root,
        issue_excerpt=issue_excerpt,
        visual_hints=hints,
    )
    config_path = agent_repo_root() / ".ai-figma-flutter.yml"
    if not config_path.is_file():
        raise LlmError("Missing .ai-figma-flutter.yml for repair context LLM")
    agent_settings = load_settings(config_path)
    api_key = agent_settings.llm_api_key()
    if not api_key:
        raise LlmError("LLM API key missing for repair context stage")
    model = _resolve_context_model(settings) or agent_settings.resolved_llm_generate_model()
    client = create_llm_client(
        provider=agent_settings.resolved_llm_provider(),
        api_key=api_key,
        model=model,
        require_strict_json_schema=agent_settings.llm_require_strict_json_schema,
        temperature=0.1,
        top_p=agent_settings.llm_top_p,
        reasoning=agent_settings.resolved_llm_reasoning(),
        max_retries=agent_settings.llm_max_retries,
        max_output_tokens=agent_settings.llm_max_output_tokens,
    )
    spec = repair_ticket_output_spec(strict=agent_settings.llm_require_strict_json_schema)
    system_prompt = (
        "Synthesize a RepairTicket JSON for a figma-flutter-agent compiler failure. "
        "Use processed artifacts only; do not invent figma node ids."
    )

    def _run() -> RepairTicket:
        base = client
        if not isinstance(base, BaseLlmClient):
            raise LlmError("LLM client does not support structured repair ticket")
        raw = base._request_generation(
            prompt,
            system_prompt=system_prompt,
            figma_reference_png=None,
            output_spec=spec,
            analytics_span_name="repair_context_ticket",
        )
        data = json.loads(raw)
        return RepairTicket.model_validate(data)

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.exception("Repair context LLM failed")
        raise LlmError(f"Repair context LLM failed: {exc}") from exc
