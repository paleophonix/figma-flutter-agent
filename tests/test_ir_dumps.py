"""Screen IR debug dumps under ``.debug/ir`` (project) or render session fallback."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
from figma_flutter_agent.debug.paths import screen_ir_dump_path
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.render_log import bind_render_log_session, clear_render_log_session
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _minimal_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:1",
        name="Frame",
        type=NodeType.STACK,
        children=[],
    )


def test_write_screen_ir_snapshot_writes_project_ir_only(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    clear_render_log_session()
    project = tmp_path / "demo_app"
    project.mkdir()
    bind_render_log_session(run_id="ir01", feature_name="sign_up", project_dir=project)

    screen_ir = default_screen_ir(_minimal_tree())
    paths = write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="sign_up_and_sign_in",
        screen_ir=screen_ir,
        project_dir=project,
    )
    assert len(paths) == 1
    project_path = screen_ir_dump_path(project, "sign_up_and_sign_in", "llm_validated")
    assert paths == [project_path]
    assert project_path.is_file()
    assert '"screenIr"' in project_path.read_text(encoding="utf-8")
    clear_render_log_session()


def test_write_screen_ir_snapshot_render_session_without_project(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    clear_render_log_session()
    bind_render_log_session(run_id="ir02", feature_name="sign_up")

    screen_ir = default_screen_ir(_minimal_tree())
    paths = write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="sign_up",
        screen_ir=screen_ir,
        project_dir=None,
    )
    assert len(paths) == 1
    assert paths[0].parent.name == "ir"
    assert paths[0].name == "llm_validated.json"
    clear_render_log_session()
