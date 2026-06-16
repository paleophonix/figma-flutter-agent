"""Internal callback routes for the job runner."""

from __future__ import annotations

import secrets
from typing import Any

from aiohttp import web

from discord_bot.db import JobStore


async def handle_preview_session(
    request: web.Request,
    *,
    store: JobStore,
    expected_secret: str,
) -> web.Response:
    """Return preview session metadata for the local companion."""
    if not secrets.compare_digest(request.headers.get("X-Internal-Secret", ""), expected_secret):
        return web.Response(status=401, text="unauthorized")
    job_id = request.match_info.get("job_id", "")
    job = await store.get_job(job_id)
    if job is None:
        return web.json_response({"error": "not_found"}, status=404)
    return web.json_response(
        {
            "jobId": job.id,
            "projectDir": job.project_dir,
            "featureSlug": job.feature_slug,
            "tokenHash": job.preview_token_hash,
            "fixedPreviewUrl": job.fixed_preview_url,
            "adaptivePreviewUrl": job.adaptive_preview_url,
        }
    )


def register_internal_routes(
    app: web.Application,
    *,
    store: JobStore,
    expected_secret: str,
    bot: Any,
) -> None:
    """Mount internal routes on the webhook application."""

    async def preview_handler(request: web.Request) -> web.Response:
        return await handle_preview_session(
            request,
            store=store,
            expected_secret=expected_secret,
        )

    app.router.add_get("/internal/jobs/{job_id}/preview", preview_handler)
