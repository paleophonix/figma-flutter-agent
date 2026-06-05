"""Geometry planner emit integration and sidecar gate."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.layout_common import GEOMETRY_PLANNER_MARKER
from figma_flutter_agent.generator.layout_flex_reconcile import apply_flex_guards_from_tree
from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_render_layout_includes_geometry_planner_marker() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=360.0, height=640.0),
        children=[
            CleanDesignTreeNode(
                id="cta",
                name="CTA",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(
                    left=20.0,
                    top=500.0,
                    width=320.0,
                    height=48.0,
                ),
            ),
        ],
    )
    normalized = normalize_clean_tree(tree, use_geometry_planner=True)
    files = render_layout_file(
        normalized,
        skip_layout_reconcile=True,
        feature_name="geometry_marker",
        uses_svg=False,
        use_geometry_planner=True,
    )
    layout = files["lib/generated/geometry_marker_layout.dart"]
    assert GEOMETRY_PLANNER_MARKER in layout


def test_flex_reconcile_skips_ast_when_geometry_planner_marker_present() -> None:
    source = f"""{GEOMETRY_PLANNER_MARKER}
class Demo {{
  Widget build() => Container();
}}
"""
    root = CleanDesignTreeNode(id="root", name="Root", type=NodeType.COLUMN)
    assert apply_flex_guards_from_tree(source, root, run_ast_pass=True) == source


def test_layout_emit_no_raw_effect_blur_in_generator() -> None:
    """T4 grep-gate: blur must route through render_units helpers."""
    root = Path(__file__).resolve().parents[1] / "src" / "figma_flutter_agent" / "generator"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "render_units.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "blurRadius: {effect.blur" in text:
            offenders.append(str(path.relative_to(root.parent.parent)))
    assert not offenders
