"""Telegram Bot API webhook routes."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from discord_bot.api.deps import get_bot, get_settings, get_store
from discord_bot.db import AutocloseMode, JobStatus
from discord_bot.services.close_notify import deliver_issue_closed_notice
from discord_bot.services.issues import IssueService
from discord_bot.services.telegram import TelegramNotifier

router = APIRouter(tags=["telegram"])


@router.post("/webhooks/telegram")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Handle Telegram callback queries (close issue button)."""
    settings = get_settings(request)
    secret = settings.yaml.internal.callback_secret
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret and header and not secrets.compare_digest(header, secret):
        raise HTTPException(status_code=401, detail="unauthorized")

    payload: dict[str, Any] = await request.json()
    callback = payload.get("callback_query")
    if not callback:
        return {"status": "ignored"}

    data = str(callback.get("data") or "")
    if not data.startswith("close_issue:"):
        return {"status": "ignored"}

    job_id = data.removeprefix("close_issue:")
    store = get_store(request)
    bot = get_bot(request)
    job = await store.get_job(job_id)
    if job is None:
        return {"status": "not_found"}

    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    notifier = TelegramNotifier(settings)
    expected_chat = await notifier.resolve_chat_id(store, job.discord_user_id)
    if not expected_chat or chat_id != expected_chat:
        return {"status": "forbidden"}

    mode = await store.get_autoclose_mode(job.discord_user_id)
    if mode != AutocloseMode.USER.value:
        return {"status": "forbidden"}

    if job.status != JobStatus.FEEDBACK_ISSUE_CREATED:
        return {"status": "closed"}

    await IssueService(settings).close_issue(job)
    await store.update_job(job_id, status=JobStatus.ISSUE_CLOSED.value)
    refreshed = await store.get_job(job_id)
    if refreshed is not None:
        issue_url = refreshed.issue_url or refreshed.gitlab_issue_url or ""
        await deliver_issue_closed_notice(
            bot=bot,
            settings=settings,
            store=store,
            job=refreshed,
            issue_url=issue_url,
        )
    return {"status": "ok"}
