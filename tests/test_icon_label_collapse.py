"""LAW-COLLAPSE-CONSERVE: icon+label groups must not collapse to a lone SVG."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.assets.composite_icons import is_compact_vector_icon_export_node
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.boundaries.assets import resolve_discovered_vector_asset_keys
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing, StackPlacement


def _icon_label_group(*, with_hoisted_key: bool = True) -> CleanDesignTreeNode:
    vector = CleanDesignTreeNode(
        id="vec",
        name="Star",
        type=NodeType.VECTOR,
        sizing=Sizing(width=20.0, height=20.0),
        vector_asset_key="assets/icons/star.svg",
        stack_placement=StackPlacement(left=30.0, width=20.0, height=20.0),
    )
    text = CleanDesignTreeNode(
        id="text",
        name="4.7",
        type=NodeType.TEXT,
        text="4.7",
        sizing=Sizing(width=23.0, height=19.0),
        style=NodeStyle(font_size=16.0, font_weight="w700"),
        stack_placement=StackPlacement(left=0.0, width=23.0, height=19.0),
    )
    inner = CleanDesignTreeNode(
        id="inner",
        name="Review",
        type=NodeType.STACK,
        sizing=Sizing(width=53.0, height=20.0),
        children=[text, vector],
    )
    return CleanDesignTreeNode(
        id="group",
        name="Ratings",
        type=NodeType.STACK,
        sizing=Sizing(width=53.0, height=20.0),
        vector_asset_key="assets/icons/star.svg" if with_hoisted_key else None,
        stack_placement=StackPlacement(width=53.0, height=20.0),
        children=[inner],
    )


def test_compact_vector_export_rejects_text_subtree() -> None:
    group = _icon_label_group()
    assert is_compact_vector_icon_export_node(group) is False


def test_icon_label_group_emits_text_and_vector_not_parent_svg() -> None:
    body = render_node_body(_icon_label_group(), uses_svg=True)
    compact = body.replace("\n", "")
    assert "Text('4.7'" in compact
    assert "SvgPicture.asset('assets/icons/star.svg'" in compact
    assert compact.count("SvgPicture.asset('assets/icons/star.svg'") >= 1
    parent_only = (
        "SvgPicture.asset('assets/icons/star.svg', width: 53.0, height: 20.0, fit: BoxFit.fill)"
        in compact
    )
    assert not parent_only


def test_lone_compact_vector_still_exports_single_svg() -> None:
    icon = CleanDesignTreeNode(
        id="icon",
        name="Icon",
        type=NodeType.VECTOR,
        sizing=Sizing(width=20.0, height=20.0),
        vector_asset_key="assets/icons/star.svg",
    )
    host = CleanDesignTreeNode(
        id="host",
        name="Host",
        type=NodeType.STACK,
        sizing=Sizing(width=20.0, height=20.0),
        vector_asset_key="assets/icons/star.svg",
        children=[icon],
    )
    assert is_compact_vector_icon_export_node(host) is True
    body = render_node_body(host, uses_svg=True)
    assert "SvgPicture.asset('assets/icons/star.svg'" in body
    assert "Text(" not in body


def test_vector_key_hoist_skips_text_subtree(tmp_path: Path) -> None:
    icons_dir = tmp_path / "assets" / "icons"
    icons_dir.mkdir(parents=True)
    svg_path = icons_dir / "star_vec.svg"
    svg_path.write_text("<svg/>", encoding="utf-8")

    vector = CleanDesignTreeNode(
        id="vec:1",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=20.0, height=20.0),
        vector_asset_key="assets/icons/star_vec.svg",
    )
    text = CleanDesignTreeNode(
        id="text:1",
        name="Free",
        type=NodeType.TEXT,
        text="Free",
        sizing=Sizing(width=30.0, height=17.0),
    )
    group = CleanDesignTreeNode(
        id="group:1",
        name="Shipping",
        type=NodeType.STACK,
        sizing=Sizing(width=63.0, height=17.0),
        children=[text, vector],
    )
    resolve_discovered_vector_asset_keys(group, tmp_path)
    assert group.vector_asset_key is None
