"""OpenCode → OpenRouter connectivity smoke before repair/fix write steps."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.dev.opencode.client import OpenCodeClient
from figma_flutter_agent.dev.opencode.opencode_policy import OPENCODE_REPAIR_AGENT
from figma_flutter_agent.dev.opencode.opencode_response import (
    extract_opencode_prompt_error,
    extract_opencode_token_usage,
    opencode_provider_reached,
)
from figma_flutter_agent.errors import FigmaFlutterError

PREFLIGHT_PROMPT = "Reply with exactly: OK"
PREFLIGHT_TIMEOUT_SEC = 90.0


async def verify_opencode_openrouter_connectivity(
    *,
    base_url: str,
    password: str = "",
    username: str = "opencode",
    worktree_directory: str | None = None,
    model: str,
    reasoning_effort: str | None = None,
    timeout_sec: float = PREFLIGHT_TIMEOUT_SEC,
) -> None:
    """Prove OpenCode serve can reach the configured OpenRouter model.

    Args:
        base_url: OpenCode server root URL.
        password: Optional basic-auth password.
        username: Basic-auth username.
        worktree_directory: Optional git worktree directory header.
        model: Normalized ``openrouter/...`` model slug for repair.
        reasoning_effort: Optional OpenCode reasoning effort override.
        timeout_sec: HTTP timeout for the smoke ``prompt_message``.

    Raises:
        FigmaFlutterError: When the smoke prompt errors or returns zero LLM tokens.
    """
    client = OpenCodeClient(
        base_url=base_url,
        username=username,
        password=password,
        worktree_directory=worktree_directory,
        timeout_sec=timeout_sec,
    )
    session_id = await client.create_session(title="openrouter-preflight")
    logger.info(
        "OpenCode provider preflight dispatch model={} timeout_sec={}",
        model,
        timeout_sec,
    )
    try:
        response = await client.prompt_message(
            session_id,
            text=PREFLIGHT_PROMPT,
            agent=OPENCODE_REPAIR_AGENT,
            model=model,
            reasoning_effort=reasoning_effort,
        )
    except FigmaFlutterError:
        await client.abort_session(session_id)
        raise
    provider_error = extract_opencode_prompt_error(response)
    tokens_in, tokens_out = extract_opencode_token_usage(response)
    if provider_error:
        await client.abort_session(session_id)
        raise FigmaFlutterError(
            "OpenCode serve could not reach OpenRouter during provider preflight: "
            f"{provider_error}. Stop OpenCode on :4096 and re-run wizard debug so serve "
            "restarts with OPENROUTER_API_KEY from .env."
        )
    if not opencode_provider_reached(response):
        await client.abort_session(session_id)
        raise FigmaFlutterError(
            "OpenCode provider preflight returned zero LLM tokens (repair would hang "
            "before the first OpenRouter call). Verify OPENROUTER_API_KEY, restart "
            "opencode serve with debug_pipeline.restart_opencode_serve_with_overlay: true, "
            f"and confirm model {model!r} is available on OpenRouter."
        )
    logger.info(
        "OpenCode provider preflight ok model={} tokens_in={} tokens_out={}",
        model,
        tokens_in,
        tokens_out,
    )
