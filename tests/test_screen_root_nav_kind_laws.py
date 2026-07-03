"""Screen-root nav_bottom_bar downgrade and cached IR compatibility laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.ir_cache import (
    assert_cached_screen_ir_compatible,
    ir_cache_metadata_for_write,
)
from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot
from figma_flutter_agent.debug.ir_load import resolve_screen_ir_dump_path
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.generator.ir.validate.root_kind import (
    heal_screen_root_control_kind,
    heal_screen_root_nav_bottom_bar_kind,
    nav_bottom_bar_kind_contradicts_clean_node,
    screen_root_kind_contradicts_clean_node,
)
from figma_flutter_agent.pipeline.llm import load_cached_ir_llm_outcome
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
    ScreenIr,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
)
from figma_flutter_agent.sync.snapshot import hash_clean_tree


def _screen_root() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="7342:2818",
        name="Home Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=430.0, height=932.0),
        children=[
            CleanDesignTreeNode(id="child", name="Body", type=NodeType.TEXT, text="Body"),
        ],
    )


def test_screen_root_vetoes_input_rating_on_artboard() -> None:
    """Law: ScreenRootControlKindVetoLaw — full artboards cannot be input_rating roots."""
    clean_root = _screen_root()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id=clean_root.id,
            kind=WidgetIrKind.INPUT_RATING,
            children=[],
        )
    )
    assert screen_root_kind_contradicts_clean_node(WidgetIrKind.INPUT_RATING, clean_root) is True
    assert heal_screen_root_control_kind(screen_ir, clean_root) is True
    assert screen_ir.root.kind == WidgetIrKind.STACK


def test_nav_bottom_bar_kind_contradicts_screen_frame() -> None:
    assert nav_bottom_bar_kind_contradicts_clean_node(_screen_root()) is True


def test_nav_bottom_bar_kind_allows_compact_dock() -> None:
    dock = CleanDesignTreeNode(
        id="dock",
        name="Bottom Navigation",
        type=NodeType.BOTTOM_NAV,
        sizing=Sizing(width=430.0, height=108.0),
        children=[
            CleanDesignTreeNode(id="home", name="Home", type=NodeType.TEXT, text="Home"),
        ],
    )
    assert nav_bottom_bar_kind_contradicts_clean_node(dock) is False


def test_heal_screen_root_nav_bottom_bar_kind_downgrades_to_stack() -> None:
    clean_root = _screen_root()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="7342:2818",
            kind=WidgetIrKind.NAV_BOTTOM_BAR,
            children=[],
        )
    )
    assert heal_screen_root_nav_bottom_bar_kind(screen_ir, clean_root) is True
    assert screen_ir.root.kind == WidgetIrKind.STACK


def test_cached_ir_rejected_when_processed_tree_changed(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    tree = _screen_root()
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id=tree.id, kind=WidgetIrKind.STACK, children=[]),
    )
    write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="home",
        screen_ir=screen_ir,
        project_dir=project,
        extra=ir_cache_metadata_for_write(tree),
    )
    path = resolve_screen_ir_dump_path(project, "home")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cleanTreeHash"] = "stale-hash"
    path.write_text(json.dumps(payload), encoding="utf-8")
    generation = FlutterGenerationResponse(screen_ir=screen_ir)
    with pytest.raises(FlutterProjectError, match="cleanTreeHash mismatch"):
        assert_cached_screen_ir_compatible(generation, tree, dump_path=path)


def test_cached_ir_load_heals_poisoned_nav_root(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    tree = _screen_root()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id=tree.id,
            kind=WidgetIrKind.NAV_BOTTOM_BAR,
            children=[],
        ),
    )
    write_screen_ir_snapshot(
        stage="llm_validated",
        feature_name="home",
        screen_ir=screen_ir,
        project_dir=project,
        extra=ir_cache_metadata_for_write(tree),
    )
    outcome = load_cached_ir_llm_outcome(
        __import__("loguru").logger,
        settings=Settings(),
        project_dir=project,
        resolved_feature="home",
        clean_tree=tree,
        tokens=DesignTokens(),
    )
    loaded = outcome.llm_result.generation
    assert loaded is not None
    assert loaded.screen_ir is not None
    assert loaded.screen_ir.root.kind == WidgetIrKind.STACK


def test_ir_cache_fingerprint_matches_hash_clean_tree() -> None:
    tree = _screen_root()
    settings = Settings()
    meta = ir_cache_metadata_for_write(tree, settings=settings)
    assert meta["cleanTreeHash"] == hash_clean_tree(tree)
    assert meta["cleanRootFigmaId"] == tree.id
    assert meta["parserVersion"]
    assert meta["irSchemaVersion"] == "1"
    assert meta["generationConfigHash"]
