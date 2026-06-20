"""Re-run Flutter screen capture to refresh the debug mirror passport."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.capture import run_project_debug_capture
from figma_flutter_agent.debug.paths import (
    CAPTURE_MANIFEST_JSON,
    CAPTURE_PNG,
    screen_root,
)
from figma_flutter_agent.dev.opencode.capture_passport import flutter_capture_trusted
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace
from figma_flutter_agent.dev.view_render_plan import load_clean_tree_from_debug, planned_for_capture
from figma_flutter_agent.errors import FigmaFlutterError


@dataclass(frozen=True)
class CaptureVerifyResult:
    """Outcome of a post-repair Flutter capture verify pass."""

    passed: bool
    payload: dict[str, Any]


def _sync_capture_artifacts_to_mirror(
    *,
    project_dir: Path,
    feature: str,
    debug_mirror: Path,
) -> None:
    """Copy capture passport and PNG from screen root into the worktree mirror."""
    src_root = screen_root(project_dir, feature)
    for name in (CAPTURE_MANIFEST_JSON, CAPTURE_PNG):
        src = src_root / name
        if src.is_file():
            shutil.copy2(src, debug_mirror / name)


async def run_capture_verify(
    *,
    workspace: RepairWorkspace,
    settings: Settings,
    project_dir: Path,
    feature: str,
) -> CaptureVerifyResult:
    """Run warm-sandbox Flutter capture and refresh mirror ``capture.json``.

    Args:
        workspace: Active repair workspace.
        settings: Agent settings.
        project_dir: Flutter project root.
        feature: Screen feature slug.

    Returns:
        CaptureVerifyResult with ``passed`` when ``flutterCaptureOk`` is true.
    """
    if not settings.agent.dev.debug_capture:
        payload = {
            "step": "capture_verify",
            "passed": False,
            "reason_code": "DEBUG_CAPTURE_DISABLED",
        }
        _write_state(workspace.state_dir, payload)
        return CaptureVerifyResult(passed=False, payload=payload)

    bundle_path = screen_root(project_dir, feature) / "screen.dart"
    if not bundle_path.is_file():
        mirror_bundle = workspace.debug_mirror / "screen.dart"
        if mirror_bundle.is_file():
            bundle_path = mirror_bundle
        else:
            payload = {
                "step": "capture_verify",
                "passed": False,
                "reason_code": "MISSING_SCREEN_BUNDLE",
            }
            _write_state(workspace.state_dir, payload)
            return CaptureVerifyResult(passed=False, payload=payload)

    clean_tree = load_clean_tree_from_debug(project_dir, feature)
    try:
        capture_plan = planned_for_capture(
            project_dir,
            feature_name=feature,
            bundle_path=bundle_path,
            settings=settings,
            clean_tree=clean_tree,
        )
    except (FileNotFoundError, ValueError, FigmaFlutterError) as exc:
        payload = {
            "step": "capture_verify",
            "passed": False,
            "reason_code": "CAPTURE_PLAN_FAILED",
            "error": str(exc),
        }
        _write_state(workspace.state_dir, payload)
        return CaptureVerifyResult(passed=False, payload=payload)

    logger.info("Repair capture verify: feature={} (flutter test)", feature)
    outcome = await run_project_debug_capture(
        project_dir=project_dir,
        feature_name=feature,
        settings=settings,
        planned_files=capture_plan.planned,
        clean_tree=clean_tree,
    )
    if outcome is None:
        payload = {
            "step": "capture_verify",
            "passed": False,
            "reason_code": "CAPTURE_DISABLED",
        }
        _write_state(workspace.state_dir, payload)
        return CaptureVerifyResult(passed=False, payload=payload)

    _sync_capture_artifacts_to_mirror(
        project_dir=project_dir,
        feature=feature,
        debug_mirror=workspace.debug_mirror,
    )
    manifest_path = workspace.debug_mirror / CAPTURE_MANIFEST_JSON
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            manifest = loaded

    passed = outcome.flutter_capture_ok and flutter_capture_trusted(manifest)
    payload = {
        "step": "capture_verify",
        "passed": passed,
        "flutterCaptureOk": outcome.flutter_capture_ok,
        "warnings": list(outcome.warnings),
        "reason_code": None if passed else "FLUTTER_CAPTURE_BLOCKED",
    }
    _write_state(workspace.state_dir, payload)
    return CaptureVerifyResult(passed=passed, payload=payload)


def _write_state(state_dir: Path, payload: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "capture_verify.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
