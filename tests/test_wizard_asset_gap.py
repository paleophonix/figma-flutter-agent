"""Tests for wizard asset export gap detection."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.dev.wizard.asset_gap import (
    exportable_icon_ids_for_tree,
    icon_ids_covered_on_disk,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_exportable_icon_ids_skip_flattened_render_boundary_children() -> None:
    figma_root = {
        "id": "1:1",
        "type": "FRAME",
        "children": [
            {
                "id": "1:2",
                "name": "Logo",
                "type": "VECTOR",
                "visible": True,
            },
            {
                "id": "1:3",
                "name": "Glyph",
                "type": "VECTOR",
                "visible": True,
            },
        ],
    }
    clean_tree = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Logo",
                type=NodeType.VECTOR,
                render_boundary=True,
                flatten_figma_node_ids=("1:3",),
            ),
            CleanDesignTreeNode(
                id="1:3",
                name="Glyph",
                type=NodeType.VECTOR,
            ),
        ],
    )
    expected = exportable_icon_ids_for_tree(
        figma_root,
        clean_tree,
        exclude_node_ids=frozenset({"1:1"}),
    )
    assert expected == frozenset({"1:2"})


def test_icon_ids_covered_on_disk_finds_render_boundary_exports(tmp_path: Path) -> None:
    illustrations = tmp_path / "assets" / "illustrations"
    illustrations.mkdir(parents=True)
    (illustrations / "render_boundary_1_2.svg").write_text("<svg/>", encoding="utf-8")
    covered = icon_ids_covered_on_disk(tmp_path, frozenset({"1:2"}))
    assert covered == frozenset({"1:2"})
