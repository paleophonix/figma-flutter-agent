# Repair pipeline

Compiler auto-repair orchestrated by the control plane: processed `.debug` snapshot → RepairTicket → epistemic diagnose fan-out → build → gates → GitLab MR.

## Purpose

Enqueue headless repair jobs that run in a git worktree on the **agent repo**, using OpenCode `serve` for build stages and deterministic `ruff`/`pytest` gates before MR publish.

## Usage Example

```python
from control_panel.services.repair_jobs import enqueue_repair

result = await enqueue_repair(
    settings=settings,
    repair_store=repair_store,
    generation_store=job_store,
    arq_pool=arq_pool,
    parent_generation_job_id="job_abc123",
    principal="api-client-1",
    origin="api",
)
```

REST: `POST /v1/repair-jobs` with `X-API-Key` header.

## LLM Context

- Processed artifacts live under `.repair/debug/<project>/<feature>/` inside the worktree.
- `RepairTicket` JSON is posted to the linked GitLab issue after the Context stage.
- Coarse issue status only: `queued`, `running`, `mr_ready`, `failed`, `cancelled`.
- Queue concurrency is **1** — jobs chain serially.
