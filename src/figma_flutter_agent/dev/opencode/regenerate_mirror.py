"""Re-run generate after compiler-layer repair and refresh the debug mirror."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.paths import RAW_JSON, screen_root
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace
from figma_flutter_agent.dev.wizard.preflight import build_run_plan
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.pipeline.run import run_pipeline

_LLM_VALIDATED = "llm_validated.json"
_LLM_PARSED = "llm_parsed.json"


@dataclass(frozen=True)
class RegenerateResult:
    """Outcome of a post-repair screen regenerate."""

    passed: bool
    payload: dict[str, Any]


def _resolve_regenerate_inputs(
    *,
    project_dir: Path,
    feature: str,
    debug_mirror: Path,
) -> tuple[Path | None, Path | None, str | None]:
    """Return ``(from_dump, from_ir_path, figma_url)`` for offline replay."""
    dump_candidates: list[Path] = []
    mirror_raw = debug_mirror / RAW_JSON
    if mirror_raw.is_file():
        dump_candidates.append(mirror_raw)
    try:
        plan = build_run_plan(project_dir=project_dir, screen_name=feature)
        if plan.dump_path.is_file():
            dump_candidates.append(plan.dump_path)
    except (FileNotFoundError, ValueError, FigmaFlutterError):
        plan = None

    from_dump = dump_candidates[0] if dump_candidates else None
    from_ir_path: Path | None = None
    for name in (_LLM_VALIDATED, _LLM_PARSED):
        candidate = debug_mirror / name
        if candidate.is_file():
            from_ir_path = candidate
            break

    figma_url: str | None = None
    if plan is not None:
        figma_url = plan.figma_url
    return from_dump, from_ir_path, figma_url


def refresh_debug_mirror(
    *,
    workspace: RepairWorkspace,
    project_dir: Path,
    feature: str,
) -> Path:
    """Copy fresh ``screen_root`` artifacts into the worktree debug mirror.

    Args:
        workspace: Active repair workspace.
        project_dir: Flutter project root.
        feature: Screen feature slug.

    Returns:
        Path to the refreshed mirror directory.

    Raises:
        FigmaFlutterError: When the source screen root is missing.
    """
    src = screen_root(project_dir, feature)
    if not src.is_dir():
        msg = f"regenerate screen root missing: {src.as_posix()}"
        raise FigmaFlutterError(msg)
    dest = workspace.debug_mirror
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


async def run_regenerate_after_compiler_repair(
    *,
    workspace: RepairWorkspace,
    settings: Settings,
    project_dir: Path,
    feature: str,
) -> RegenerateResult:
    """Replay generate with repaired compiler code and cached screen inputs.

    Uses ``raw.json`` and cached screen IR from the debug mirror when present so
    the verify pass does not call the LLM again.

    Args:
        workspace: Active repair workspace (worktree + mirror paths).
        settings: Agent settings loaded for the repair run.
        project_dir: Flutter project root.
        feature: Screen feature slug.

    Returns:
        RegenerateResult with serialized payload for the reasoning chain.
    """
    from_dump, from_ir_path, figma_url = _resolve_regenerate_inputs(
        project_dir=project_dir,
        feature=feature,
        debug_mirror=workspace.debug_mirror,
    )
    if from_dump is None:
        payload = {
            "step": "regenerate",
            "passed": False,
            "reason_code": "MISSING_DUMP",
            "notes": "No raw.json in debug mirror and no batch dump for screen",
        }
        _write_state(workspace.state_dir, payload)
        return RegenerateResult(passed=False, payload=payload)

    use_cached_ir = from_ir_path is not None
    logger.info(
        "Repair regenerate: feature={} from_dump={} from_ir={}",
        feature,
        from_dump.as_posix(),
        from_ir_path.as_posix() if from_ir_path else "-",
    )
    try:
        result = await run_pipeline(
            settings,
            figma_url=figma_url,
            project_dir=project_dir,
            feature_name=feature,
            from_dump=from_dump,
            from_ir=use_cached_ir,
            from_ir_path=from_ir_path,
            require_figma_token=False,
            force_live_fetch=False,
            regenerate_templates=False,
        )
    except Exception as exc:
        logger.exception("Repair regenerate failed for feature={}", feature)
        payload = {
            "step": "regenerate",
            "passed": False,
            "reason_code": "PIPELINE_ERROR",
            "error": str(exc),
            "from_dump": from_dump.as_posix(),
            "from_ir": use_cached_ir,
        }
        _write_state(workspace.state_dir, payload)
        return RegenerateResult(passed=False, payload=payload)

    refresh_debug_mirror(workspace=workspace, project_dir=project_dir, feature=feature)
    payload = {
        "step": "regenerate",
        "passed": True,
        "from_dump": from_dump.as_posix(),
        "from_ir": use_cached_ir,
        "from_ir_path": from_ir_path.as_posix() if from_ir_path else None,
        "written_files": list(result.written_files),
        "run_id": result.run_id,
        "dart_errors_log": result.dart_errors_log,
    }
    _write_state(workspace.state_dir, payload)
    return RegenerateResult(passed=True, payload=payload)


def _write_state(state_dir: Path, payload: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "regenerate.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
