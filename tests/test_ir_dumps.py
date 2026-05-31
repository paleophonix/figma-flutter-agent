"""Screen IR debug dumps under .figma_debug/ir and logs/renders/.../ir/."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
from figma_flutter_agent.debug.paths import screen_ir_dump_path
from figma_flutter_agent.generator.ir_tree import default_screen_ir
from figma_flutter_agent.render_log import bind_render_log_session, clear_render_log_session
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _minimal_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:1",
        name="Frame",
        type=NodeType.STACK,
        children=[],
    )


def test_write_screen_ir_snapshot_project_and_render_log(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
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
    assert len(paths) == 2
    project_path = screen_ir_dump_path(project, "sign_up_and_sign_in", "llm_validated")
    assert project_path in paths
    assert project_path.is_file()
    assert '"screenIr"' in project_path.read_text(encoding="utf-8")

    render_ir = tmp_path / "logs" / "renders"
    ir_files = list(render_ir.glob("*/ir/llm_validated.json"))
    assert len(ir_files) == 1
    clear_render_log_session()
