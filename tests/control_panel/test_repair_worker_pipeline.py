"""Control-panel repair worker uses wizard headless pipeline by default."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from control_panel.db.enums import RepairJobStatus
from control_panel.workers import tasks


@pytest.mark.asyncio
async def test_run_repair_job_skips_mr_when_task_not_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    job.status = RepairJobStatus.QUEUED
    job.parent_generation_job_id = "gen-1"
    job.flutter_project_dir = None
    job.feature_slug = "login"

    parent = MagicMock()
    parent.project_dir = "/tmp/demo_app"
    parent.feature_slug = "login"

    repair_store = AsyncMock()
    repair_store.get_job.return_value = job
    generation_store = AsyncMock()
    generation_store.get_job.return_value = parent

    workspace = MagicMock()
    workspace.worktree.as_posix.return_value = "/tmp/wt"
    outcome = MagicMock()
    outcome.stopped = False
    outcome.stop_reason = ""
    outcome.task_completed = False
    outcome.workspace = workspace

    headless = AsyncMock(return_value=outcome)
    publish = AsyncMock()
    update = AsyncMock()
    monkeypatch.setattr(tasks, "run_headless_repair_case", headless)
    monkeypatch.setattr(tasks, "run_repair_publish", publish)
    monkeypatch.setattr(tasks, "update_repair_job_and_publish", update)
    monkeypatch.setattr(tasks, "maybe_enqueue_next_repair", AsyncMock())
    monkeypatch.setattr(tasks, "set_repair_queue_depth", lambda *_args, **_kwargs: None)

    settings = MagicMock()
    settings.yaml.repair.enabled = True
    settings.yaml.repair.use_legacy_pipeline = False
    settings.yaml.repair.agent_repo_path = ""

    ctx = {
        "settings": settings,
        "store": generation_store,
        "repair_store": repair_store,
        "event_redis": None,
        "arq_pool": None,
    }

    await tasks.run_repair_job(ctx, "repair-2")

    publish.assert_not_awaited()
    update.assert_awaited()
    failed_call = [
        call
        for call in update.await_args_list
        if call.kwargs.get("status") == RepairJobStatus.FAILED
    ]
    assert failed_call


@pytest.mark.asyncio
async def test_run_repair_job_uses_headless_pipeline_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = MagicMock()
    job.status = RepairJobStatus.QUEUED
    job.parent_generation_job_id = "gen-1"
    job.flutter_project_dir = None
    job.feature_slug = "login"
    job.project_slug = None

    parent = MagicMock()
    parent.project_dir = "/tmp/demo_app"
    parent.feature_slug = "login"

    repair_store = AsyncMock()
    repair_store.get_job.return_value = job

    generation_store = AsyncMock()
    generation_store.get_job.return_value = parent

    workspace = MagicMock()
    workspace.worktree.as_posix.return_value = "/tmp/wt"
    outcome = MagicMock()
    outcome.stopped = True
    outcome.stop_reason = "budget_exhausted"
    outcome.workspace = workspace

    headless = AsyncMock(return_value=outcome)
    monkeypatch.setattr(tasks, "run_headless_repair_case", headless)
    legacy = AsyncMock()
    monkeypatch.setattr(tasks, "run_repair_pipeline", legacy)
    monkeypatch.setattr(tasks, "update_repair_job_and_publish", AsyncMock())
    monkeypatch.setattr(tasks, "maybe_enqueue_next_repair", AsyncMock())
    monkeypatch.setattr(tasks, "set_repair_queue_depth", lambda *_args, **_kwargs: None)

    settings = MagicMock()
    settings.yaml.repair.enabled = True
    settings.yaml.repair.use_legacy_pipeline = False
    settings.yaml.repair.agent_repo_path = ""

    ctx = {
        "settings": settings,
        "store": generation_store,
        "repair_store": repair_store,
        "event_redis": None,
        "arq_pool": None,
    }

    await tasks.run_repair_job(ctx, "repair-1")

    headless.assert_awaited_once()
    legacy.assert_not_awaited()
