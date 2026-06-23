"""Re-run generate after compiler-layer repair and refresh the debug mirror."""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.paths import (
    FIGMA_DEBUG_DIR,
    RAW_JSON,
    screen_debug_safe_feature,
    screen_debug_safe_project,
    screen_root,
)
from figma_flutter_agent.dev.opencode.gates import ensure_worktree_poetry_env
from figma_flutter_agent.dev.opencode.repair_log import emit_repair_progress
from figma_flutter_agent.dev.opencode.repair_project_sandbox import ensure_flutter_project_sandbox
from figma_flutter_agent.dev.opencode.scope_enforcement import collect_plan_target_files
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace
from figma_flutter_agent.dev.opencode.worktree_runtime import (
    isolated_poetry_env_for_worktree,
    resolve_orchestrator_ast_compiler_path,
)
from figma_flutter_agent.dev.wizard.preflight import build_run_plan
from figma_flutter_agent.errors import FigmaFlutterError

_LLM_VALIDATED = "llm_validated.json"
_LLM_PARSED = "llm_parsed.json"
_PIPELINE_CHILD_SCRIPT = "regenerate_pipeline_child.py"
_REGENERATE_HEARTBEAT_SEC = 30


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


def resolve_regenerate_debug_screen_root(
    *,
    workspace: RepairWorkspace,
    source_project_dir: Path,
    sandbox_project_dir: Path,
    feature: str,
) -> Path:
    """Return the screen debug root written by the isolated worktree regenerate subprocess.

    ``RepairRegenerateMirrorRootLaw``: ``poetry -P <worktree>`` runs the pipeline with
    ``agent_repo_root()`` inside the worktree checkout, so fresh artifacts land under
    ``<worktree>/.debug/<sandbox_label>/<feature>/``. The orchestrator must not read
    ``screen_root(sandbox_project_dir)`` on the parent checkout (wrong repo + label).

    Args:
        workspace: Active repair workspace.
        source_project_dir: User Flutter project root (for example ``apps/limbo``).
        sandbox_project_dir: Repair-local sandbox copy under ``.repair/candidate/``.
        feature: Screen feature slug.

    Returns:
        Existing screen debug directory to copy into the worktree mirror.

    Raises:
        FigmaFlutterError: When no candidate screen root exists on disk.
    """
    safe_feature = screen_debug_safe_feature(feature)
    sandbox_label = screen_debug_safe_project(sandbox_project_dir)
    candidates = [
        workspace.worktree
        / FIGMA_DEBUG_DIR
        / sandbox_label
        / safe_feature,
        screen_root(source_project_dir, feature),
        screen_root(sandbox_project_dir, feature),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    tried = ", ".join(path.as_posix() for path in candidates)
    msg = f"regenerate screen root missing after subprocess; tried: {tried}"
    raise FigmaFlutterError(msg)


@dataclass(frozen=True)
class MirrorRefreshResult:
    """Paths after copying regenerate debug artifacts into the worktree mirror."""

    mirror_dir: Path
    source_dir: Path


def refresh_debug_mirror(
    *,
    workspace: RepairWorkspace,
    source_project_dir: Path,
    sandbox_project_dir: Path,
    feature: str,
) -> Path:
    """Copy fresh regenerate debug artifacts into the worktree debug mirror.

    Args:
        workspace: Active repair workspace.
        source_project_dir: User Flutter project root.
        sandbox_project_dir: Repair-local Flutter sandbox used by the subprocess.
        feature: Screen feature slug.

    Returns:
        Mirror paths for the refreshed mirror and the source screen root.

    Raises:
        FigmaFlutterError: When the regenerate debug screen root is missing.
    """
    src = resolve_regenerate_debug_screen_root(
        workspace=workspace,
        source_project_dir=source_project_dir,
        sandbox_project_dir=sandbox_project_dir,
        feature=feature,
    )
    dest = workspace.debug_mirror
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    logger.info(
        "Repair regenerate mirror refreshed from={} to={}",
        src.as_posix(),
        dest.as_posix(),
    )
    return MirrorRefreshResult(mirror_dir=dest, source_dir=src)


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


def resolve_regenerate_orchestrator_root() -> Path:
    """Return the wizard checkout root that owns the pipeline child entry script."""
    return resolve_regenerate_pipeline_child_script().resolve().parents[4]


async def _regenerate_heartbeat(
    proc: asyncio.subprocess.Process,
    *,
    started_at: float,
) -> None:
    """Emit periodic wizard progress while the regenerate subprocess runs."""
    while proc.returncode is None:
        await asyncio.sleep(_REGENERATE_HEARTBEAT_SEC)
        if proc.returncode is not None:
            return
        elapsed = int(time.monotonic() - started_at)
        emit_repair_progress("regenerate", f"pipeline running ({elapsed}s)")


async def _run_pipeline_in_worktree(
    worktree: Path,
    *,
    request: dict[str, Any],
    state_dir: Path,
    timeout_sec: int,
    orchestrator_root: Path,
) -> dict[str, Any]:
    """Run generate via ``poetry -P <worktree>`` so repaired compiler code is used."""
    ensure_worktree_poetry_env(worktree)
    request_path = state_dir / "regenerate_pipeline_request.json"
    result_path = state_dir / "regenerate_pipeline_result.json"
    request_path.write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    child_script = resolve_regenerate_pipeline_child_script()
    compiler = resolve_orchestrator_ast_compiler_path(orchestrator_root)
    if compiler is not None:
        emit_repair_progress(
            "regenerate",
            f"orchestrator ast_compiler: {compiler.name}",
        )
    else:
        emit_repair_progress(
            "regenerate",
            "orchestrator ast_compiler missing; worktree may use slow dart run",
        )
    emit_repair_progress("regenerate", "pipeline subprocess starting")
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
    env = isolated_poetry_env_for_worktree(orchestrator_root=orchestrator_root)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    started_at = time.monotonic()
    heartbeat = asyncio.create_task(_regenerate_heartbeat(proc, started_at=started_at))
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=float(timeout_sec))
    except TimeoutError:
        proc.kill()
        await proc.wait()
        elapsed = int(time.monotonic() - started_at)
        emit_repair_progress("regenerate", f"timeout after {elapsed}s (limit {timeout_sec}s)")
        return {
            "passed": False,
            "error": f"regenerate timed out after {timeout_sec}s",
            "reason_code": "REGENERATE_TIMEOUT",
        }
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat
    elapsed = int(time.monotonic() - started_at)
    emit_repair_progress("regenerate", f"pipeline subprocess finished ({elapsed}s)")
    if proc.returncode != 0 and not result_path.is_file():
        output = ((stdout or b"") + (stderr or b"")).decode("utf-8", errors="replace")
        return {"passed": False, "error": output[-4000:] or f"exit code {proc.returncode}"}
    if not result_path.is_file():
        return {"passed": False, "error": "regenerate subprocess did not write result.json"}
    loaded = json.loads(result_path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {"passed": False, "error": "invalid result payload"}


_RAW_REPLAY_MARKERS = (
    "src/figma_flutter_agent/parser/",
    "/generator/ir/",
    "generator/ir/validate",
)


def resolve_regenerate_proof_mode(plan_payload: dict[str, Any] | None) -> str:
    """Select regenerate replay mode from plan compiler target layers.

    Args:
        plan_payload: Validated executive plan JSON when available.

    Returns:
        ``raw_replay`` when parser/IR/validate layers changed; else ``cached_ir``.
    """
    if not isinstance(plan_payload, dict):
        return "cached_ir"
    for target in collect_plan_target_files(plan_payload):
        lowered = target.lower()
        if any(marker in lowered for marker in _RAW_REPLAY_MARKERS):
            return "raw_replay"
    return "cached_ir"


def _should_use_cached_ir(
    *,
    plan_payload: dict[str, Any] | None,
    from_ir_path: Path | None,
) -> bool:
    if resolve_regenerate_proof_mode(plan_payload) == "raw_replay":
        return False
    return from_ir_path is not None


async def run_regenerate_after_compiler_repair(
    *,
    workspace: RepairWorkspace,
    settings: Settings,
    project_dir: Path,
    feature: str,
    plan_payload: dict[str, Any] | None = None,
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
    source_project_dir = project_dir
    sandbox_project_dir = ensure_flutter_project_sandbox(workspace, source_project_dir)
    timeout_sec = settings.agent.debug_pipeline.loops.regenerate_timeout_sec
    orchestrator_root = resolve_regenerate_orchestrator_root()
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
            "proof_mode": resolve_regenerate_proof_mode(plan_payload),
        }
        _write_state(workspace.state_dir, payload)
        return RegenerateResult(passed=False, payload=payload)

    use_cached_ir = _should_use_cached_ir(
        plan_payload=plan_payload,
        from_ir_path=from_ir_path,
    )
    proof_mode = resolve_regenerate_proof_mode(plan_payload)
    logger.info(
        "Repair regenerate: feature={} from_dump={} from_ir={} proof_mode={}",
        feature,
        from_dump.as_posix(),
        from_ir_path.as_posix() if from_ir_path else "-",
        proof_mode,
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
            timeout_sec=timeout_sec,
            orchestrator_root=orchestrator_root,
        )
        if not pipeline_outcome.get("passed"):
            payload = {
                "step": "regenerate",
                "passed": False,
                "reason_code": str(pipeline_outcome.get("reason_code") or "PIPELINE_ERROR"),
                "error": str(pipeline_outcome.get("error") or "pipeline subprocess failed"),
                "from_dump": from_dump.as_posix(),
                "from_ir": use_cached_ir,
                "proof_mode": proof_mode,
            }
            _write_state(workspace.state_dir, payload)
            return RegenerateResult(passed=False, payload=payload)
        try:
            mirror_refresh = refresh_debug_mirror(
                workspace=workspace,
                source_project_dir=source_project_dir,
                sandbox_project_dir=sandbox_project_dir,
                feature=feature,
            )
        except FigmaFlutterError as exc:
            logger.exception("Repair regenerate mirror refresh failed for feature={}", feature)
            payload = {
                "step": "regenerate",
                "passed": False,
                "reason_code": "MIRROR_REFRESH_FAILED",
                "error": str(exc),
                "from_dump": from_dump.as_posix(),
                "from_ir": use_cached_ir,
                "proof_mode": proof_mode,
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
            "proof_mode": proof_mode,
        }
        _write_state(workspace.state_dir, payload)
        return RegenerateResult(passed=False, payload=payload)

    payload = {
        "step": "regenerate",
        "passed": True,
        "from_dump": from_dump.as_posix(),
        "from_ir": use_cached_ir,
        "proof_mode": proof_mode,
        "from_ir_path": from_ir_path.as_posix() if from_ir_path else None,
        "source_project_dir": source_project_dir.resolve().as_posix(),
        "sandbox_project_dir": sandbox_project_dir.resolve().as_posix(),
        "mirror_source_dir": mirror_refresh.source_dir.resolve().as_posix(),
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
