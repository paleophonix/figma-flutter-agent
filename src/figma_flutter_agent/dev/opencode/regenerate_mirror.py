"""Re-run generate after compiler-layer repair and refresh the debug mirror."""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.paths import RAW_JSON, screen_root
from figma_flutter_agent.dev.opencode.gates import ensure_worktree_poetry_env
from figma_flutter_agent.dev.opencode.repair_project_sandbox import ensure_flutter_project_sandbox
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace
from figma_flutter_agent.dev.opencode.worktree_runtime import isolated_poetry_env
from figma_flutter_agent.dev.wizard.preflight import build_run_plan
from figma_flutter_agent.errors import FigmaFlutterError

_LLM_VALIDATED = "llm_validated.json"
_LLM_PARSED = "llm_parsed.json"
_PIPELINE_CHILD_SCRIPT = "regenerate_pipeline_child.py"


def resolve_regenerate_pipeline_child_script() -> Path:
    """Return the orchestrator-owned pipeline child entry script path.

    The subprocess runs under ``poetry -P <worktree>`` so compiler edits load from
    the worktree package, but the entry script always comes from the active
    orchestrator checkout (not the frozen worktree snapshot).
    """
    script = Path(__file__).resolve().parent / _PIPELINE_CHILD_SCRIPT
    if not script.is_file():
        msg = f"regenerate pipeline child script missing: {script.as_posix()}"
        raise FigmaFlutterError(msg)
    return script


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


def _build_pipeline_request(
    *,
    figma_url: str | None,
    project_dir: Path,
    feature: str,
    from_dump: Path,
    from_ir_path: Path | None,
    use_cached_ir: bool,
) -> dict[str, Any]:
    """Serialize kwargs for the worktree pipeline subprocess."""
    return {
        "figma_url": figma_url,
        "project_dir": project_dir.resolve().as_posix(),
        "feature_name": feature,
        "from_dump": from_dump.resolve().as_posix(),
        "from_ir": use_cached_ir,
        "from_ir_path": from_ir_path.resolve().as_posix() if from_ir_path else None,
        "require_figma_token": False,
        "force_live_fetch": False,
        "regenerate_templates": False,
        "pipeline_invocation": "repair_regenerate",
    }


async def _run_pipeline_in_worktree(
    worktree: Path,
    *,
    request: dict[str, Any],
    state_dir: Path,
) -> dict[str, Any]:
    """Run generate via ``poetry -P <worktree>`` so repaired compiler code is used."""
    ensure_worktree_poetry_env(worktree)
    request_path = state_dir / "regenerate_pipeline_request.json"
    result_path = state_dir / "regenerate_pipeline_result.json"
    request_path.write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    child_script = resolve_regenerate_pipeline_child_script()
    cmd = [
        "poetry",
        "-P",
        str(worktree.resolve()),
        "run",
        "python",
        str(child_script),
        str(request_path),
        str(result_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=isolated_poetry_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0 and not result_path.is_file():
        output = ((stdout or b"") + (stderr or b"")).decode("utf-8", errors="replace")
        return {"passed": False, "error": output[-4000:] or f"exit code {proc.returncode}"}
    if not result_path.is_file():
        return {"passed": False, "error": "regenerate subprocess did not write result.json"}
    loaded = json.loads(result_path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {"passed": False, "error": "invalid result payload"}


async def run_regenerate_after_compiler_repair(
    *,
    workspace: RepairWorkspace,
    settings: Settings,
    project_dir: Path,
    feature: str,
) -> RegenerateResult:
    """Replay generate with repaired compiler code and cached screen inputs.

    Uses ``raw.json`` and cached screen IR from the debug mirror when present so
    the verify pass does not call the LLM again. Pipeline execution is isolated to
    ``workspace.worktree`` via ``poetry -P`` so repaired compiler modules are used.

    Args:
        workspace: Active repair workspace (worktree + mirror paths).
        settings: Agent settings for orchestrator compatibility (subprocess reloads).
        project_dir: Flutter project root.
        feature: Screen feature slug.

    Returns:
        RegenerateResult with serialized payload for the reasoning chain.
    """
    _ = settings
    source_project_dir = project_dir
    sandbox_project_dir = ensure_flutter_project_sandbox(workspace, source_project_dir)
    from_dump, from_ir_path, figma_url = _resolve_regenerate_inputs(
        project_dir=source_project_dir,
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
        pipeline_request = _build_pipeline_request(
            figma_url=figma_url,
            project_dir=sandbox_project_dir,
            feature=feature,
            from_dump=from_dump,
            from_ir_path=from_ir_path,
            use_cached_ir=use_cached_ir,
        )
        pipeline_outcome = await _run_pipeline_in_worktree(
            workspace.worktree,
            request=pipeline_request,
            state_dir=workspace.state_dir,
        )
        if not pipeline_outcome.get("passed"):
            error = str(pipeline_outcome.get("error") or "pipeline subprocess failed")
            raise FigmaFlutterError(error)
    except FigmaFlutterError as exc:
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

    refresh_debug_mirror(
        workspace=workspace,
        project_dir=sandbox_project_dir,
        feature=feature,
    )
    payload = {
        "step": "regenerate",
        "passed": True,
        "from_dump": from_dump.as_posix(),
        "from_ir": use_cached_ir,
        "from_ir_path": from_ir_path.as_posix() if from_ir_path else None,
        "source_project_dir": source_project_dir.resolve().as_posix(),
        "sandbox_project_dir": sandbox_project_dir.resolve().as_posix(),
        "written_files": list(pipeline_outcome.get("written_files") or []),
        "run_id": pipeline_outcome.get("run_id"),
        "dart_errors_log": pipeline_outcome.get("dart_errors_log"),
        "worktree_isolated": True,
    }
    _write_state(workspace.state_dir, payload)
    return RegenerateResult(passed=True, payload=payload)


def _write_state(state_dir: Path, payload: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "regenerate.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
