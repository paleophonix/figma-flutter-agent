"""Webhook routes."""

from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, Header, HTTPException, Request

from discord_bot.api.deps import get_bot, get_settings, get_store
from discord_bot.webhooks import github as github_handlers
from discord_bot.webhooks import gitlab as gitlab_handlers

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(default=""),
) -> dict[str, str]:
    """Accept GitLab issue and merge request webhooks."""
    settings = get_settings(request)
    expected = settings.yaml.internal.gitlab_webhook_secret
    if not expected or not secrets.compare_digest(x_gitlab_token, expected):
        raise HTTPException(status_code=401, detail="unauthorized")
    payload = await request.json()
    store = get_store(request)
    bot = get_bot(request)

    async def _notify() -> None:
        await gitlab_handlers.process_gitlab_payload(
            payload,
            store=store,
            bot=bot,
            settings=settings,
        )

    asyncio.create_task(_notify())
    return {"status": "ok"}


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
) -> dict[str, str]:
    """Accept GitHub issue and pull request webhooks."""
    settings = get_settings(request)
    secret = settings.yaml.internal.github_webhook_secret
    body = await request.body()
    if not github_handlers.verify_signature(
        secret=secret,
        body=body,
        signature_header=x_hub_signature_256,
    ):
        raise HTTPException(status_code=401, detail="unauthorized")
    payload = await request.json()
    store = get_store(request)
    bot = get_bot(request)

    async def _notify() -> None:
        await github_handlers.process_github_payload(
            payload,
            event_name=x_github_event,
            store=store,
            bot=bot,
            settings=settings,
        )

    asyncio.create_task(_notify())
    return {"status": "ok"}
