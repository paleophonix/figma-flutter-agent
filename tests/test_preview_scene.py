"""Preview scene conversion tests."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.preview.scene import (
    preview_css_color,
    preview_scene_from_clean_tree,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.schemas.geometry import GeometryFrame, GeomRect
from figma_flutter_agent.schemas.style import NodeStyle

ROOT = Path(__file__).resolve().parents[1]
CONSENT_FIXTURE = ROOT / "tests" / "fixtures" / "layouts" / "consent_checkbox_row.json"


def _load_consent_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode.model_validate(
        json.loads(CONSENT_FIXTURE.read_text(encoding="utf-8")),
    )


def test_preview_scene_from_clean_tree_rect() -> None:
    tree = _load_consent_tree()
    scene = preview_scene_from_clean_tree(tree)
    assert scene.width == 390
    assert scene.height == 844
    assert any(node.type == "rect" for node in scene.nodes)


def test_preview_scene_from_clean_tree_text() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        sizing={"width": 200, "height": 100},
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Label",
                type=NodeType.TEXT,
                text="Welcome back",
                style=NodeStyle(textColor="#111111", fontSize=28, fontWeight="700"),
                geometry_frame=GeometryFrame(
                    world_aabb=GeomRect(x=24, y=120, width=240, height=32),
                ),
            ),
        ],
    )
    scene = preview_scene_from_clean_tree(tree)
    text_nodes = [node for node in scene.nodes if node.type == "text"]
    assert len(text_nodes) == 1
    assert text_nodes[0].text == "Welcome back"


def test_preview_scene_preserves_paint_order() -> None:
    first = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        sizing={"width": 100, "height": 100},
        children=[
            CleanDesignTreeNode(
                id="back",
                name="Back",
                type=NodeType.STACK,
                style=NodeStyle(backgroundColor="#111111"),
                sizing={"width": 100, "height": 100},
            ),
            CleanDesignTreeNode(
                id="front",
                name="Front",
                type=NodeType.STACK,
                style=NodeStyle(backgroundColor="#FFFFFF"),
                sizing={"width": 50, "height": 50},
            ),
        ],
    )
    scene = preview_scene_from_clean_tree(first)
    ids = [node.id for node in scene.nodes if node.type == "rect"]
    assert ids.index("back") < ids.index("front")


def test_preview_scene_uses_absolute_bounds() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        sizing={"width": 200, "height": 200},
        children=[
            CleanDesignTreeNode(
                id="placed",
                name="Placed",
                type=NodeType.STACK,
                style=NodeStyle(backgroundColor="#FF0000"),
                geometry_frame=GeometryFrame(
                    world_aabb=GeomRect(x=12, y=24, width=80, height=40),
                ),
            ),
        ],
    )
    scene = preview_scene_from_clean_tree(tree)
    rect = next(node for node in scene.nodes if node.id == "placed")
    assert rect.x == 0
    assert rect.y == 0
    assert rect.width == 80
    assert rect.height == 40


def test_preview_css_color_converts_flutter_argb() -> None:
    assert preview_css_color("0xFFFFFFFF") == "rgba(255, 255, 255, 1.000)"
    assert preview_css_color("#111111") == "#111111"


def test_preview_scene_converts_argb_background_and_fill() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        sizing={"width": 100, "height": 100},
        style=NodeStyle(backgroundColor="0xFFFFFFFF"),
        children=[
            CleanDesignTreeNode(
                id="cta",
                name="CTA",
                type=NodeType.STACK,
                style=NodeStyle(backgroundColor="0xFF2563EB"),
                geometry_frame=GeometryFrame(
                    world_aabb=GeomRect(x=0, y=40, width=100, height=40),
                ),
            ),
        ],
    )
    scene = preview_scene_from_clean_tree(tree)
    assert scene.background == "rgba(255, 255, 255, 1.000)"
    cta = next(node for node in scene.nodes if node.id == "cta")
    assert cta.fill == "rgba(37, 99, 235, 1.000)"


def test_preview_scene_does_not_emit_semantic_kinds() -> None:
    scene = preview_scene_from_clean_tree(_load_consent_tree())
    payload = scene.model_dump(mode="json")
    serialized = json.dumps(payload)
    assert "semantic" not in serialized.lower()
    assert "widgetIr" not in serialized
    assert "looks_like" not in serialized
