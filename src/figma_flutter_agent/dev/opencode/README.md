# dev/opencode

## Purpose

Local OpenCode repair pipeline: Run Gate (M0), workspace orchestration, OpenRouter read steps, OpenCode build repair, deterministic check/fix/capture gates, and summarize routing (M0–M6).

## Usage Example

```python
import asyncio
from pathlib import Path

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.dev.opencode import (
    evaluate_run_gate,
    run_repair_pipeline,
    ensure_opencode_serve,
    OpenCodeClient,
)

async def main() -> None:
    settings = load_settings()
    project_dir = Path("../demo_app")
    feature = "login_version_1"
    gate = evaluate_run_gate(project_dir, feature)
    await ensure_opencode_serve(
        base_url=settings.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
    )
    client = OpenCodeClient(base_url=settings.opencode_base_url)
    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project_dir,
        feature=feature,
        opencode_client=client,
    )
    print(gate.verdict, outcome.stop_reason)

asyncio.run(main())
```

Wizard entry: `poetry run figma-flutter -i` → **debug**.

## LLM Context

After Data Refresh, `evaluate_run_gate` writes `run_manifest.json`. `run_repair_pipeline` copies `.debug/<project>/<feature>/` into worktree `.repair/debug/`, runs recognise→summarize with cumulative `reasoning_chain.json`, and persists step JSON under `.repair/state/`. When `debug_pipeline.trace.enabled`, a durable copy lands under `.traces/<project>/<feature>/<MMDD-HHMM>-<run_id>/` and PostHog `$ai_trace_id` matches `run_id`.
