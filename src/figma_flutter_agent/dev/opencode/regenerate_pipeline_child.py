"""Subprocess entry: run generate pipeline with worktree-installed compiler."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.pipeline.run import run_pipeline


def _optional_path(raw: str | None) -> Path | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return Path(text) if text else None


async def _run_request(payload: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    result = await run_pipeline(
        settings,
        figma_url=payload.get("figma_url"),
        project_dir=Path(str(payload["project_dir"])),
        feature_name=payload.get("feature_name"),
        from_dump=_optional_path(payload.get("from_dump")),
        from_ir=bool(payload.get("from_ir")),
        from_ir_path=_optional_path(payload.get("from_ir_path")),
        require_figma_token=bool(payload.get("require_figma_token", False)),
        force_live_fetch=bool(payload.get("force_live_fetch", False)),
        regenerate_templates=bool(payload.get("regenerate_templates", False)),
    )
    return {
        "passed": True,
        "written_files": list(result.written_files),
        "run_id": result.run_id,
        "dart_errors_log": result.dart_errors_log,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: regenerate_pipeline_child <request.json> <result.json>", file=sys.stderr)
        return 2
    request_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    try:
        outcome = asyncio.run(_run_request(payload))
    except Exception as exc:
        outcome = {"passed": False, "error": str(exc)}
    result_path.write_text(json.dumps(outcome, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if outcome.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
