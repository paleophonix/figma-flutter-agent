"""Run Gate (M0): deterministic build identity before agent pipeline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.debug.paths import (
    CAPTURE_MANIFEST_JSON,
    DART_ERRORS_JSON,
    screen_root,
)
from figma_flutter_agent.debug.run_meta import (
    INCOMPLETE_RUN_STATUSES,
    TERMINAL_FAILURE_RUN_STATUSES,
    is_run_meta_gate_trusted,
    read_run_meta,
)
from figma_flutter_agent.dev.opencode.capture_passport import (
    CaptureRunState,
    capture_passport_summary,
    capture_run_state,
)
from figma_flutter_agent.dev.opencode.failure_class import (
    FailureClass,
    agent_board_for_case_mode,
    case_mode_for_verdict,
)

RUN_MANIFEST_JSON = "run_manifest.json"
_FFA_RUN_ID_COMMENT = re.compile(r"FFA_RUN_ID:\s*([^\s]+)")
_FFA_RUN_ID_CONST = re.compile(r"static const String ffaRunId = '([^']+)'")

_RESUME_SAFE_VERDICTS = frozenset({FailureClass.NO_SERVE})


def gate_blocks_new_run(verdict: FailureClass) -> bool:
    """Return whether Run Gate blocks a fresh repair pipeline start."""
    return verdict in {FailureClass.NO_SERVE, FailureClass.UNKNOWN_BLOCKED}


def gate_blocks_pipeline(*, verdict: FailureClass, resume: bool) -> bool:
    """Return whether Run Gate should stop the orchestrator for this invocation.

      ``RepairResumeRunGateParityLaw``: resume may continue when the only blocker is
    ``NO_SERVE`` (stale served probe) because the worktree already holds compiler edits.
    """
    if verdict == FailureClass.UNKNOWN_BLOCKED:
        return True
    if verdict == FailureClass.NO_SERVE:
        return not resume
    return False


def resume_safe_gate_verdicts() -> frozenset[FailureClass]:
    """Verdicts the wizard may bypass when resuming an existing worktree."""
    return _RESUME_SAFE_VERDICTS


@dataclass(frozen=True)
class RunGateResult:
    """Run Gate evaluation output."""

    feature: str
    screen_root: Path
    verdict: FailureClass
    case_mode: str
    agent_board: str
    pipeline_run_id: str
    candidate_build_run_id: str
    committed_build_run_id: str
    served_build_run_id: str
    writeback: str
    served_probe_present: bool
    candidate_available: bool
    manifest_path: Path
    allowed_questions: tuple[str, ...]
    forbidden_questions: tuple[str, ...]

    def to_manifest_dict(self) -> dict[str, Any]:
        """Serialize run_manifest.json body."""
        return {
            "feature": self.feature,
            "pipeline_run_id": self.pipeline_run_id,
            "candidate_build_run_id": self.candidate_build_run_id,
            "committed_build_run_id": self.committed_build_run_id,
            "served_build_run_id": self.served_build_run_id,
            "writeback": self.writeback,
            "served_probe_present": self.served_probe_present,
            "verdict": self.verdict.value,
            "case_mode": self.case_mode,
            "agent_board": self.agent_board,
            "candidate_available": self.candidate_available,
            "allowed_questions": list(self.allowed_questions),
            "forbidden_questions": list(self.forbidden_questions),
            "stages": {},
            "change_proof": {
                "fix_proven": self.verdict == FailureClass.FRESH_OK,
            },
            "capture_passport": capture_passport_summary(
                _load_capture_manifest(self.screen_root),
            ),
        }


def probe_served_run_id(project_dir: Path, feature_name: str) -> str | None:
    """File-level served_run_id probe from debug screen.dart or project lib."""
    return probe_served_run_id_for_screen_dir(screen_root(project_dir, feature_name))


def probe_served_run_id_for_screen_dir(screen_dir: Path) -> str | None:
    """Read ``FFA_RUN_ID`` stamp from a screen debug directory ``screen.dart``."""
    screen_dart = screen_dir / "screen.dart"
    if not screen_dart.is_file():
        return None
    text = screen_dart.read_text(encoding="utf-8", errors="replace")
    for pattern in (_FFA_RUN_ID_COMMENT, _FFA_RUN_ID_CONST):
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _load_capture_manifest(screen_dir: Path) -> dict[str, Any]:
    path = screen_dir / CAPTURE_MANIFEST_JSON
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _has_analyze_errors(screen_dir: Path) -> bool:
    path = screen_dir / DART_ERRORS_JSON
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    if isinstance(data, list):
        return len(data) > 0
    if isinstance(data, dict):
        errors = data.get("errors") or data.get("events")
        if isinstance(errors, list):
            return len(errors) > 0
    return False


def evaluate_run_gate(project_dir: Path, feature_name: str) -> RunGateResult:
    """Evaluate Run Gate from debug artifacts and emit run_manifest.json.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug.

    Returns:
        RunGateResult with verdict and persisted manifest path.
    """
    screen_dir = screen_root(project_dir, feature_name)
    meta = read_run_meta(project_dir, feature_name)

    pipeline_run_id = meta.pipeline_run_id if meta else ""
    candidate_id = meta.candidate_build_run_id if meta else pipeline_run_id
    committed_id = (
        meta.committed_build_run_id
        if meta and meta.committed_build_run_id
        else (pipeline_run_id or "unknown")
    )
    writeback = meta.writeback if meta else "skipped"
    status = meta.status if meta else "legacy"
    served_probe = probe_served_run_id(project_dir, feature_name)
    served_id = served_probe or "unknown"

    verdict = FailureClass.UNKNOWN_BLOCKED
    candidate_available = (screen_dir / "screen.dart").is_file()

    if not meta or not pipeline_run_id:
        # RepairForensicEntryLaw: failed generate may skip run.meta.json while still
        # emitting screen.dart + dart-errors.json — route to forensic repair, not NO_SERVE.
        verdict = FailureClass.CANDIDATE_ONLY if candidate_available else FailureClass.NO_SERVE
    elif not is_run_meta_gate_trusted(meta):
        verdict = FailureClass.UNKNOWN_BLOCKED
    elif status in TERMINAL_FAILURE_RUN_STATUSES:
        verdict = FailureClass.ROLLED_BACK
    elif status in INCOMPLETE_RUN_STATUSES:
        verdict = FailureClass.CANDIDATE_ONLY if candidate_available else FailureClass.UNKNOWN_BLOCKED
    elif status == "completed":
        if writeback == "rollback" or writeback == "failed":
            verdict = FailureClass.ROLLED_BACK
        elif writeback == "committed" and pipeline_run_id == committed_id:
            capture = _load_capture_manifest(screen_dir)
            captured_run = str(capture.get("captured_run_id") or capture.get("runId") or "")
            run_state = capture_run_state(capture)
            if run_state == CaptureRunState.RAN_FAIL:
                verdict = FailureClass.CAPTURE_FAILED
            elif run_state == CaptureRunState.RAN_OK:
                if captured_run and captured_run not in ("", served_id, committed_id):
                    verdict = FailureClass.STALE_CAPTURE
                elif _has_analyze_errors(screen_dir):
                    verdict = FailureClass.CANDIDATE_ONLY
                elif served_probe is None:
                    verdict = FailureClass.NO_SERVE
                elif served_probe != committed_id:
                    verdict = FailureClass.CANDIDATE_ONLY
                else:
                    verdict = FailureClass.FRESH_OK
            elif _has_analyze_errors(screen_dir):
                verdict = FailureClass.CANDIDATE_ONLY
            elif served_probe is None:
                verdict = FailureClass.NO_SERVE
            elif served_probe != committed_id:
                verdict = FailureClass.CANDIDATE_ONLY
            else:
                verdict = FailureClass.CAPTURE_PENDING
        elif candidate_available and writeback != "committed":
            verdict = FailureClass.CANDIDATE_ONLY
        else:
            verdict = FailureClass.UNKNOWN_BLOCKED
    elif writeback == "rollback" or writeback == "failed":
        verdict = FailureClass.ROLLED_BACK
    elif writeback == "committed" and pipeline_run_id == committed_id:
        capture = _load_capture_manifest(screen_dir)
        captured_run = str(capture.get("captured_run_id") or capture.get("runId") or "")
        run_state = capture_run_state(capture)
        if run_state == CaptureRunState.RAN_FAIL:
            verdict = FailureClass.CAPTURE_FAILED
        elif run_state == CaptureRunState.RAN_OK:
            if captured_run and captured_run not in ("", served_id, committed_id):
                verdict = FailureClass.STALE_CAPTURE
            elif _has_analyze_errors(screen_dir):
                verdict = FailureClass.CANDIDATE_ONLY
            elif served_probe is None:
                verdict = FailureClass.NO_SERVE
            elif served_probe != committed_id:
                verdict = FailureClass.CANDIDATE_ONLY
            else:
                verdict = FailureClass.FRESH_OK
        elif _has_analyze_errors(screen_dir):
            verdict = FailureClass.CANDIDATE_ONLY
        elif served_probe is None:
            verdict = FailureClass.NO_SERVE
        elif served_probe != committed_id:
            verdict = FailureClass.CANDIDATE_ONLY
        else:
            verdict = FailureClass.CAPTURE_PENDING
    elif candidate_available and writeback != "committed":
        verdict = FailureClass.CANDIDATE_ONLY
    else:
        verdict = FailureClass.UNKNOWN_BLOCKED

    case_mode = case_mode_for_verdict(verdict)
    board = agent_board_for_case_mode(case_mode)

    if case_mode == "SCREEN":
        allowed = ("visual fidelity", "layout law", "component law")
        forbidden: tuple[str, ...] = ()
    elif case_mode == "FORENSIC":
        allowed = ("why generation/write/capture failed",)
        forbidden = ("why visible UI is wrong in Chrome",)
    else:
        allowed = ()
        forbidden = ("all screen diagnosis",)

    result = RunGateResult(
        feature=feature_name,
        screen_root=screen_dir,
        verdict=verdict,
        case_mode=case_mode,
        agent_board=board,
        pipeline_run_id=pipeline_run_id or "unknown",
        candidate_build_run_id=candidate_id or "unknown",
        committed_build_run_id=committed_id,
        served_build_run_id=served_id or "unknown",
        writeback=writeback,
        served_probe_present=served_probe is not None,
        candidate_available=candidate_available,
        manifest_path=screen_dir / RUN_MANIFEST_JSON,
        allowed_questions=allowed,
        forbidden_questions=forbidden,
    )
    screen_dir.mkdir(parents=True, exist_ok=True)
    result.manifest_path.write_text(
        json.dumps(result.to_manifest_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


def load_run_manifest(project_dir: Path, feature_name: str) -> dict[str, Any]:
    """Load persisted run_manifest.json if present."""
    path = screen_root(project_dir, feature_name) / RUN_MANIFEST_JSON
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}
