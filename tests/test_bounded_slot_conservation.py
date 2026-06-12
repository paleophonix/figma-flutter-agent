"""Bounded positioned slot conservation (T2b) and runtime overflow helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.geometry.invariants.validate import (
    validate_geometry_invariants,
)
from figma_flutter_agent.generator.geometry.planner import plan_geometry_tree
from figma_flutter_agent.generator.geometry.text_metrics import predict_typography_slack
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.interaction import host_prefers_intrinsic_extent
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    TextMetricsFrame,
)
from figma_flutter_agent.validation.golden_capture.logs import collect_renderflex_overflows

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "layouts" / "bounded_order_card.json"


def _load_fixture() -> CleanDesignTreeNode:
    return CleanDesignTreeNode.model_validate(
        json.loads(_FIXTURE.read_text(encoding="utf-8"))
    )


def test_predict_typography_slack_uses_text_metrics() -> None:
    node = CleanDesignTreeNode(
        id="1:text",
        name="Label",
        type=NodeType.TEXT,
        spacing=8.0,
        text_metrics_frame=TextMetricsFrame(
            line_height_px=22.5,
            glyph_height=11.0,
            delta_top=2.0,
            font_size=15.0,
            strut_height_ratio=1.5,
            baseline_verifiable=True,
        ),
    )
    slack = predict_typography_slack(node)
    assert slack >= 13.5


def test_t2_bounded_slot_conservation_flags_tight_column() -> None:
    planned = plan_geometry_tree(_load_fixture())
    violations = validate_geometry_invariants(planned, require_layout_slots=True)
    codes = {item.code for item in violations}
    assert "t2_bounded_slot_conservation" in codes


def test_bounded_order_card_emits_column_for_intrinsic_button() -> None:
    layout = render_layout_file(
        _load_fixture(),
        feature_name="bounded_order_card",
        uses_svg=False,
    )["lib/generated/bounded_order_card_layout.dart"]
    button = next(
        node for node in _walk(_load_fixture()) if node.id == "bounded-order:button"
    )
    assert host_prefers_intrinsic_extent(button)
    button_idx = layout.find("custom-code:figma-bounded-order_action-a:button-action")
    assert button_idx >= 0
    snippet = layout[max(0, button_idx - 1500) : button_idx + 2200]
    assert "Column(mainAxisSize: MainAxisSize.min" in snippet
    assert "StackFit.loose" not in snippet or "minHeight:" in snippet


def test_collect_renderflex_overflows_parses_flutter_log() -> None:
    sample = """
══╡ EXCEPTION CAUGHT BY RENDERING LIBRARY ╞══
A RenderFlex overflowed by 11 pixels on the bottom.
The relevant error-causing widget was:
  Column
  Column:file:///E:/demo/lib/generated/history_layout.dart:31:7206
"""
    overflows = collect_renderflex_overflows(sample, "")
    assert len(overflows) == 1
    assert "11px" in overflows[0]
    assert "history_layout.dart" in overflows[0]


def _walk(root: CleanDesignTreeNode):
    yield root
    for child in root.children:
        yield from _walk(child)


@pytest.mark.skipif(not _FIXTURE.is_file(), reason="bounded_order_card fixture missing")
def test_tight_slot_fixture_present() -> None:
    assert _FIXTURE.is_file()
