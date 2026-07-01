"""Effective build identity after repair regenerate and mirror refresh."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from figma_flutter_agent.debug.paths import CAPTURE_MANIFEST_JSON, RUN_META_JSON
from figma_flutter_agent.debug.run_meta import RunMetaRecord
from figma_flutter_agent.dev.opencode.capture_passport import (
    CaptureRunState,
    capture_run_state,
)
from figma_flutter_agent.dev.opencode.failure_class import (
    FailureClass,
    agent_board_for_case_mode,
    case_mode_for_verdict,
)
from figma_flutter_agent.dev.opencode.run_gate import (
    RunGateResult,
    probe_served_run_id_for_screen_dir,
)

ProofKind = Literal["served_probe", "committed_run_meta", "missing"]


@dataclass(frozen=True)
class EffectiveBuildIdentity:
    """Runtime build ids and optional board refresh after mirror regenerate."""

    committed_run_id: str
    served_run_id: str
    served_probe_present: bool
    proof_kind: ProofKind
    writeback: str
    capture_run_state: CaptureRunState
    case_mode: str
    agent_board: str
    refreshed_from_regenerate: bool


def _load_capture_manifest(screen_dir: Path) -> dict[str, Any]:
    path = screen_dir / CAPTURE_MANIFEST_JSON
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_mirror_run_meta(debug_mirror: Path) -> RunMetaRecord | None:
    path = debug_mirror / RUN_META_JSON
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return RunMetaRecord.from_dict(data)


def reevaluate_build_identity(
    debug_mirror: Path,
    *,
    project_dir: Path,
    feature: str,
    initial_gate: RunGateResult,
    regenerate_payload: dict[str, Any] | None = None,
) -> EffectiveBuildIdentity:
    """Re-read build identity from the refreshed debug mirror.

    Args:
        debug_mirror: Repair worktree mirror for the active screen.
        project_dir: Source Flutter project root (for served probe fallback).
        feature: Screen feature slug.
        initial_gate: Run Gate snapshot from pipeline start.
        regenerate_payload: Successful regenerate step payload when present.

    Returns:
        Effective ids and board for subsequent check/capture/review gates.
    """
    refreshed = bool(regenerate_payload and regenerate_payload.get("passed"))
    regen_run_id = str(regenerate_payload.get("run_id") or "").strip() if refreshed else ""

    meta = _read_mirror_run_meta(debug_mirror)
    committed_id = (
        meta.committed_build_run_id
        if meta and meta.committed_build_run_id
        else initial_gate.committed_build_run_id
    )
    if regen_run_id:
        committed_id = regen_run_id

    mirror_probe = probe_served_run_id_for_screen_dir(debug_mirror)
    proof_kind: ProofKind = "missing"
    served_id = ""
    if mirror_probe:
        served_id = mirror_probe
        proof_kind = "served_probe"
    elif refreshed and regen_run_id:
        served_id = regen_run_id
        proof_kind = "committed_run_meta"
    elif meta and meta.committed_build_run_id:
        served_id = meta.committed_build_run_id
        proof_kind = "committed_run_meta"
    elif committed_id and committed_id != "unknown":
        served_id = committed_id
        proof_kind = "committed_run_meta"

    served_probe_present = mirror_probe is not None
    writeback = meta.writeback if meta else initial_gate.writeback
    if refreshed and regen_run_id:
        writeback = "committed"
    capture = _load_capture_manifest(debug_mirror)
    run_state = capture_run_state(capture)

    verdict = initial_gate.verdict
    if refreshed and regen_run_id:
        if run_state == CaptureRunState.RAN_FAIL:
            verdict = FailureClass.CAPTURE_FAILED
        elif run_state == CaptureRunState.RAN_OK:
            verdict = FailureClass.FRESH_OK
        elif writeback == "committed":
            verdict = FailureClass.CAPTURE_PENDING
        else:
            verdict = FailureClass.ROLLED_BACK

    case_mode = case_mode_for_verdict(verdict)

    return EffectiveBuildIdentity(
        committed_run_id=committed_id or "unknown",
        served_run_id=served_id or "unknown",
        served_probe_present=served_probe_present,
        proof_kind=proof_kind,
        writeback=writeback,
        capture_run_state=run_state,
        case_mode=case_mode,
        agent_board=agent_board_for_case_mode(case_mode),
        refreshed_from_regenerate=refreshed,
    )
