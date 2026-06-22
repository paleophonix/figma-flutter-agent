"""Tests for L6 prompt bindings and repo map slicing."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.dev.opencode.l6_context import build_l6_bindings, render_l6_template
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.repo_map import (
    deep_repo_map_json,
    resolve_deep_module_paths,
)
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace


def test_render_l6_template_replaces_placeholders() -> None:
    rendered = render_l6_template(
        "Worktree: {worktree}\nMap:\n{repo_map_deep_json}",
        {"worktree": "/tmp/wt", "repo_map_deep_json": "{}"},
    )
    assert "/tmp/wt" in rendered
    assert "{repo_map_deep_json}" not in rendered


def test_build_l6_bindings_includes_repo_map(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    repair_root = worktree / ".repair"
    state_dir = repair_root / "state"
    debug_mirror = repair_root / "debug" / "limbo" / "login"
    state_dir.mkdir(parents=True)
    debug_mirror.mkdir(parents=True)
    manifest_path = repair_root / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=repair_root,
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=manifest_path,
    )
    chain = ReasoningChain(
        steps={
            "diagnose": {
                "laws": [
                    {
                        "id": "law_row",
                        "repairShape": {"target": "emitter"},
                    }
                ]
            }
        }
    )
    bindings = build_l6_bindings(
        step="plan",
        board="forensic",
        workspace=workspace,
        feature="login",
        project_label="limbo",
        run_context={"case_mode": "FORENSIC"},
        reasoning_chain_json=chain.compact_json_for_step("plan"),
        chain=chain,
    )
    assert "generator/layout/widgets/emit/flex.py" in bindings["repo_map_deep_json"]


def test_deep_repo_map_json_includes_overflow_surfaces() -> None:
    chain = ReasoningChain(
        steps={
            "recognise": {
                "symptoms": [{"description": "RenderFlex overflow in Row"}],
            }
        }
    )
    payload = deep_repo_map_json(chain)
    assert "flex.py" in payload


def test_resolve_deep_module_paths_accepts_string_repair_shape() -> None:
    chain = ReasoningChain(
        steps={
            "diagnose": {
                "laws": [
                    {
                        "id": "law_row",
                        "repairShape": "emitter",
                    }
                ]
            }
        }
    )
    paths = resolve_deep_module_paths(chain)
    assert "generator/layout/widgets/emit/flex.py" in paths
