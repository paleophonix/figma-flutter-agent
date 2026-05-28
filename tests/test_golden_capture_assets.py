"""Golden capture asset sync and workspace selection."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement
from figma_flutter_agent.validation.golden_capture import collect_planned_asset_paths


def test_collect_planned_asset_paths_from_dart_strings() -> None:
    planned = {
        "lib/features/sign_in/sign_in_screen.dart": (
            "SvgPicture.asset('assets/icons/vector_1_3576.svg');\n"
            "Image.asset(\"assets/icons/other.svg\");"
        ),
    }
    paths = collect_planned_asset_paths(planned)
    assert paths == {
        "assets/icons/vector_1_3576.svg",
        "assets/icons/other.svg",
    }


def test_collect_planned_asset_paths_includes_layout_tree_vectors(tmp_path: Path) -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="icon",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/from_tree.svg",
            ),
        ],
    )
    paths = collect_planned_asset_paths({}, layout_tree=root)
    assert "assets/icons/from_tree.svg" in paths
