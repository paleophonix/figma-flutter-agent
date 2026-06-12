"""Load cached screen IR for offline generate."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
from figma_flutter_agent.debug.ir_load import (
    load_generation_from_ir_dump,
    resolve_screen_ir_dump_path,
)
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.materialize import materialize_screen_code_from_ir
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.pipeline.llm import load_cached_ir_llm_outcome
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, NodeType


def _minimal_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="362:319",
        name="Background",
        type=NodeType.STACK,
        children=[],
    )


def test_resolve_screen_ir_dump_path_stage_fallback(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    pre_emit = project / ".debug" / "ir" / "background_pre_emit.json"
    validated = project / ".debug" / "ir" / "background_llm_validated.json"
    pre_emit.parent.mkdir(parents=True)
    pre_emit.write_text("{}", encoding="utf-8")
    validated.write_text("{}", encoding="utf-8")

    assert resolve_screen_ir_dump_path(project, "background") == validated.resolve()


def test_resolve_screen_ir_dump_path_ignores_pre_emit_without_explicit_path(
    tmp_path: Path,
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    pre_emit = project / ".debug" / "ir" / "background_pre_emit.json"
    pre_emit.parent.mkdir(parents=True)
    pre_emit.write_text("{}", encoding="utf-8")

    with pytest.raises(FlutterProjectError, match="No cached screen IR"):
        resolve_screen_ir_dump_path(project, "background")


def test_pre_emit_dump_includes_emitter_version(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    tree = _minimal_tree()
    paths = write_screen_ir_snapshot(
        stage="pre_emit",
        feature_name="background",
        screen_ir=default_screen_ir(tree),
        project_dir=project,
    )
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    assert payload.get("emitterVersion")


def test_load_generation_from_ir_dump_roundtrip(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    tree = _minimal_tree()
    screen_ir = default_screen_ir(tree)
    write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="background",
        screen_ir=screen_ir,
        project_dir=project,
    )
    path = resolve_screen_ir_dump_path(project, "background")
    loaded = load_generation_from_ir_dump(path)

    assert loaded.screen_ir is not None
    assert loaded.screen_ir.root.figma_id == screen_ir.root.figma_id


def test_load_cached_ir_returns_screen_ir_generation(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    tree = _minimal_tree()
    write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="background",
        screen_ir=default_screen_ir(tree),
        project_dir=project,
    )
    settings = Settings()
    outcome = load_cached_ir_llm_outcome(
        __import__("loguru").logger,
        settings=settings,
        project_dir=project,
        resolved_feature="background",
        clean_tree=tree,
        tokens=DesignTokens(),
    )
    assert outcome.llm_result.generation is not None
    assert outcome.llm_result.generation.screen_ir is not None


def test_materialize_screen_emits_body_from_ir(tmp_path: Path) -> None:
    tree = _minimal_tree()
    screen_ir = default_screen_ir(tree)
    write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="background",
        screen_ir=screen_ir,
        project_dir=tmp_path,
    )
    from figma_flutter_agent.debug.ir_load import load_generation_from_ir_dump

    generation = load_generation_from_ir_dump(
        resolve_screen_ir_dump_path(tmp_path, "background"),
    )
    ctx = IrEmitContext(uses_svg=False, is_layout_root=True)
    out = materialize_screen_code_from_ir(
        generation,
        clean_tree=tree,
        feature_name="background",
        ctx=ctx,
        project_dir=tmp_path,
    )
    assert out.screen_ir is not None
    assert "BackgroundScreen" in (out.resolved_screen_code() or "")


def test_resolve_screen_ir_dump_path_missing_raises(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    with pytest.raises(FlutterProjectError, match="No cached screen IR"):
        resolve_screen_ir_dump_path(project, "background")


@pytest.mark.asyncio
async def test_run_pipeline_from_ir_skips_llm(tmp_path: Path) -> None:
    import figma_flutter_agent.pipeline.run.core as pipeline_module

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )
    dump_path = project_dir / ".debug" / "raw" / "background_layout.json"
    dump_path.parent.mkdir(parents=True)
    tree = _minimal_tree()
    dump_path.write_text(
        json.dumps(
            {
                "id": tree.id,
                "name": tree.name,
                "type": "FRAME",
                "visible": True,
                "children": [],
            }
        ),
        encoding="utf-8",
    )
    (project_dir / "screens.yaml").write_text(
        "\n".join(
            [
                "file_key: abc",
                "project_dir: .",
                "screens:",
                "  - feature: background",
                "    node_id: 362:319",
                "    dump: .debug/raw/background_layout.json",
            ]
        ),
        encoding="utf-8",
    )
    write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="background",
        screen_ir=default_screen_ir(tree),
        project_dir=project_dir,
    )

    from figma_flutter_agent.config import Settings
    from tests.helpers import pipeline_test_dependencies

    settings = Settings()
    settings = settings.model_copy(
        update={
            "agent": settings.agent.model_copy(
                update={
                    "generation": settings.agent.generation.model_copy(
                        update={"use_screen_ir": True}
                    )
                }
            )
        }
    )
    deps = pipeline_test_dependencies()
    llm_mock = AsyncMock()

    with patch.object(pipeline_module, "execute_llm_stage", llm_mock):
        await pipeline_module.run_pipeline(
            settings,
            figma_url=None,
            project_dir=project_dir,
            feature_name="background",
            dry_run=True,
            sync_enabled=False,
            from_dump=dump_path,
            from_ir=True,
            require_figma_token=False,
            deps=deps,
        )

    llm_mock.assert_not_called()
