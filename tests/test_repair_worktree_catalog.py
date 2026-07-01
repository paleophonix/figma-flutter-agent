"""Tests for repair worktree catalog and resume helpers."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.dev.opencode.checkpoint import (
    append_checkpoint,
    resolve_resume_phase_entry,
)
from figma_flutter_agent.dev.opencode.workspace import load_repair_workspace
from figma_flutter_agent.dev.opencode.worktree_catalog import (
    list_repair_worktrees_for_screen,
    resolve_worktree_screen_bundle,
)


def _write_worktree(
    repo: Path,
    *,
    case_id: str,
    project: str,
    feature: str,
    checkpoint_step: str | None = None,
    loop_round: int = 1,
    with_screen_dart: bool = True,
) -> Path:
    worktree = repo / ".worktrees" / case_id
    repair_root = worktree / ".repair"
    state_dir = repair_root / "state"
    debug_mirror = repair_root / "debug" / project / feature
    debug_mirror.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    if with_screen_dart:
        (debug_mirror / "screen.dart").write_text("// screen\n", encoding="utf-8")
    manifest = {
        "case_id": case_id,
        "project": project,
        "feature": feature,
        "debug_mirror": debug_mirror.relative_to(worktree).as_posix(),
    }
    (repair_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if checkpoint_step:
        append_checkpoint(state_dir, step=checkpoint_step, loop_round=loop_round)
    return worktree


def test_list_repair_worktrees_filters_project_screen(tmp_path: Path) -> None:
    _write_worktree(
        tmp_path,
        case_id="0620-2133-limbo-login_version_1",
        project="limbo",
        feature="login_version_1",
        checkpoint_step="repair",
        loop_round=2,
    )
    _write_worktree(
        tmp_path,
        case_id="0620-2200-limbo-feedback",
        project="limbo",
        feature="feedback",
        checkpoint_step="plan",
    )
    _write_worktree(
        tmp_path,
        case_id="0620-2210-demo-login_version_1",
        project="demo_app",
        feature="login_version_1",
    )

    entries = list_repair_worktrees_for_screen(
        tmp_path,
        project_label="limbo",
        feature="login_version_1",
    )
    assert len(entries) == 1
    assert entries[0].case_id == "0620-2133-limbo-login_version_1"
    assert entries[0].last_step == "repair"
    assert entries[0].loop_round == 2
    assert "repair" in entries[0].menu_label


def test_load_repair_workspace_from_manifest(tmp_path: Path) -> None:
    worktree = _write_worktree(
        tmp_path,
        case_id="0620-2133-limbo-login_version_1",
        project="limbo",
        feature="login_version_1",
    )
    workspace = load_repair_workspace(worktree)
    assert workspace.case_id == "0620-2133-limbo-login_version_1"
    assert workspace.debug_mirror.name == "login_version_1"
    assert workspace.state_dir == worktree / ".repair" / "state"


def test_resolve_worktree_screen_bundle_prefers_screen_dart(tmp_path: Path) -> None:
    worktree = _write_worktree(
        tmp_path,
        case_id="0620-2133-limbo-login_version_1",
        project="limbo",
        feature="login_version_1",
    )
    bundle = resolve_worktree_screen_bundle(worktree)
    assert bundle.name == "screen.dart"


def test_resolve_resume_phase_entry_after_repair(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    append_checkpoint(state_dir, step="repair", loop_round=3)
    phase, loop_round = resolve_resume_phase_entry(state_dir)
    assert phase == "check"
    assert loop_round == 3


def test_resolve_resume_phase_entry_after_aborted_repair(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    chain = {
        "steps": {
            "repair": {
                "provider_error": "Aborted",
                "noop": False,
                "filesTouched": [],
            },
        },
    }
    (state_dir / "reasoning_chain.json").write_text(json.dumps(chain), encoding="utf-8")
    append_checkpoint(state_dir, step="repair", loop_round=3)
    phase, loop_round = resolve_resume_phase_entry(state_dir)
    assert phase == "repair"
    assert loop_round == 3


def test_resolve_resume_phase_entry_after_repair_noop(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    chain = {
        "steps": {
            "plan": {
                "steps": [
                    {
                        "order": 1,
                        "actionKind": "CODE_CHANGE",
                        "targetFiles": [
                            "src/figma_flutter_agent/generator/layout/widgets/flex_sizing.py",
                        ],
                    }
                ],
            },
            "repair": {
                "noop": True,
                "incomplete": True,
                "filesTouched": [],
            },
        },
    }
    (state_dir / "reasoning_chain.json").write_text(json.dumps(chain), encoding="utf-8")
    append_checkpoint(state_dir, step="repair", loop_round=3)
    phase, loop_round = resolve_resume_phase_entry(state_dir)
    assert phase == "plan"
    assert loop_round == 3


def test_resolve_resume_phase_entry_failed_check_unknown_blocked(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    chain = {
        "steps": {
            "check": {
                "passed": False,
                "failure_class": "UNKNOWN_BLOCKED",
                "evidence": ["dart-errors.json:missing"],
            }
        }
    }
    (state_dir / "reasoning_chain.json").write_text(json.dumps(chain), encoding="utf-8")
    append_checkpoint(state_dir, step="check", loop_round=2)
    phase, loop_round = resolve_resume_phase_entry(state_dir)
    assert phase == "plan"
    assert loop_round == 2


def test_resolve_resume_phase_entry_after_recognise_enters_inspect(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    append_checkpoint(state_dir, step="recognise", loop_round=1)
    phase, loop_round = resolve_resume_phase_entry(state_dir)
    assert phase == "inspect"
    assert loop_round == 1


def test_resolve_resume_phase_entry_failed_check(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    chain = {
        "steps": {
            "check": {
                "passed": False,
                "failure_class": "PATCH_RUNTIME",
            }
        }
    }
    (state_dir / "reasoning_chain.json").write_text(json.dumps(chain), encoding="utf-8")
    append_checkpoint(state_dir, step="check", loop_round=2)
    phase, loop_round = resolve_resume_phase_entry(state_dir)
    assert phase == "diagnose"
    assert loop_round == 2
