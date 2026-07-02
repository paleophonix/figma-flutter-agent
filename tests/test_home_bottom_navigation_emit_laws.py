"""Regression tests for 9_a_home_bottom_navigation emit laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.capture_passport import flutter_capture_trusted
from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    stack_dense_absolute_overlays_preserve_stack,
    stack_should_flow_as_column,
)
from figma_flutter_agent.generator.widget_extractor import _bound_cluster_widget_root
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, ScreenIr, Sizing

_HOME_DEBUG = Path(".debug/screen/limbo/9_a_home_bottom_navigation")


def _load_home_root() -> CleanDesignTreeNode:
    path = _HOME_DEBUG / "processed.json"
    if not path.is_file():
        pytest.skip("9_a_home_bottom_navigation debug bundle unavailable")
    processed = json.loads(path.read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    from figma_flutter_agent.parser.dedup.hydrate import hydrate_pruned_cluster_instances

    hydrate_pruned_cluster_instances(root)
    return root


def _load_home_screen_ir() -> ScreenIr | None:
    path = _HOME_DEBUG / "pre_emit.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    screen_ir = payload.get("screenIr")
    if not isinstance(screen_ir, dict):
        return None
    return ScreenIr.model_validate(screen_ir)


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def test_absolute_overlay_density_preservation_law_blocks_home_column_flow() -> None:
    """Law: AbsoluteOverlayDensityPreservationLaw — dense dashboards stay Stack."""
    root = _load_home_root()
    assert stack_dense_absolute_overlays_preserve_stack(root)
    assert stack_should_flow_as_column(root) is False


def test_sectionize_rejects_dense_home_artboard() -> None:
    """Law: FixedArtboardStackPreservationLaw — dense overlay roots skip sectionize."""
    from figma_flutter_agent.generator.ir.passes.sectionize import evaluate_root_sectionize

    root = _load_home_root()
    plan = evaluate_root_sectionize(root, responsive_reflow_enabled=True)
    assert plan.activated is False
    assert plan.reject_reason == "dense_absolute_overlay_artboard"


def test_switch_hosts_segmented_options_emit_stateful_pill_control() -> None:
    """Law: StatefulSegmentedControlLaw — multi-option SWITCH hosts render pill control."""
    from figma_flutter_agent.generator.layout.widgets import render_node_body

    root = _load_home_root()
    switch = _find_node(root, "7342:2856")
    assert switch is not None
    body = render_node_body(switch, uses_svg=True)
    assert "Switch(value:" not in body
    assert "_SegmentedPillControl(" in body
    assert "'Daily'" in body and "'Weekly'" in body and "'Monthly'" in body


def test_stroked_glyph_checkbox_emits_static_metric_glyph() -> None:
    """Law: VectorCheckboxVisualLaw — metric summary checkmarks stay decorative SVG."""
    from figma_flutter_agent.generator.layout.widgets import render_node_body

    root = _load_home_root()
    checkbox = _find_node(root, "7342:2878")
    assert checkbox is not None
    body = render_node_body(
        checkbox,
        uses_svg=True,
        parent_node=root,
        parent_type=NodeType.STACK,
    )
    assert "Checkbox(" not in body
    assert "_GeneratedToggleCheckbox" not in body
    assert "check_7342_2878.svg" in body or "SvgPicture" in body


def test_extracted_widget_fixed_bounds_law_wraps_notification_icon() -> None:
    """Law: ExtractedWidgetFixedBoundsLaw — icon badge widgets get finite bounds."""
    root = _load_home_root()
    notification = _find_node(root, "7342:2848")
    assert notification is not None
    bounded = _bound_cluster_widget_root(notification, "const Inner()")
    assert "SizedBox(width: 30.0, height: 30.0" in bounded


def test_home_replay_layout_preserves_stack_and_bottom_nav() -> None:
    """Law: orchestration replay — home screen keeps Stack geometry and docked nav."""
    from figma_flutter_agent.generator.layout import render_layout_file

    root = _load_home_root()
    screen_ir = _load_home_screen_ir()
    files = render_layout_file(
        root,
        feature_name="9_a_home_bottom_navigation_laws",
        uses_svg=True,
        screen_ir=screen_ir,
        responsive_enabled=True,
    )
    compact = "".join(files.values()).replace("\n", "")
    assert "_LayoutIconNav" in compact
    assert "figma-7342_2848" in compact
    assert compact.count("Align(alignment: Alignment.centerLeft, child: Positioned(") == 0
    layout_key = next(
        (path for path in files if path.endswith("_layout.dart")),
        None,
    )
    assert layout_key is not None
    layout = files[layout_key]
    assert "Stack(clipBehavior:" in layout
    assert "Positioned(right: 36.0, width: 30.0, top: 61.0, height: 30.0" in layout
    assert "RenderFlex overflowed" not in compact


def test_capture_pending_is_not_visual_success() -> None:
    """Law: CAPTURE_PENDING cannot count as a successful visual repair."""
    manifest_path = _HOME_DEBUG / "run_manifest.json"
    if not manifest_path.is_file():
        pytest.skip("run_manifest.json unavailable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest.get("verdict") == FailureClass.CAPTURE_PENDING.value
    passport = manifest.get("capture_passport") or {}
    assert flutter_capture_trusted(passport) is False
    assert passport.get("capture_verified") is False


def test_arrow_badge_not_checkbox() -> None:
    """Law: SemanticCheckboxEvidenceLaw — direction badges are not checkbox controls."""
    from figma_flutter_agent.parser.interaction.forms import layout_fact_checkbox_control

    root = _load_home_root()
    income = _find_node(root, "7342:2867")
    expense = _find_node(root, "7342:2866")
    assert income is not None
    assert expense is not None
    assert not layout_fact_checkbox_control(income)
    assert not layout_fact_checkbox_control(expense)


def test_icon_glyph_not_checkbox() -> None:
    """Law: SemanticCheckboxEvidenceLaw — pictogram vectors are not checkbox controls."""
    from figma_flutter_agent.parser.interaction.forms import layout_fact_checkbox_control

    root = _load_home_root()
    salary = _find_node(root, "7342:2861")
    assert salary is not None
    assert not layout_fact_checkbox_control(salary)


def test_decorative_metric_checkmark_not_interactive_control() -> None:
    """Law: VectorCheckboxVisualLaw — percent metric glyphs are not toggle controls."""
    from figma_flutter_agent.parser.interaction.forms import (
        layout_fact_decorative_metric_checkmark_glyph,
        layout_fact_interactive_checkbox_control,
    )

    root = _load_home_root()
    checkbox = _find_node(root, "7342:2878")
    assert checkbox is not None
    assert layout_fact_decorative_metric_checkmark_glyph(checkbox, parent_node=root)
    assert not layout_fact_interactive_checkbox_control(checkbox, parent_node=root)


def test_painted_dashboard_card_not_multiline_field() -> None:
    """Law: PaintedCardNotFieldLaw — dashboard cards do not emit as TextField shells."""
    from figma_flutter_agent.parser.interaction.absolute_fields import (
        layout_fact_painted_dashboard_card_shell,
        layout_fact_painted_multiline_field_shell,
    )

    root = _load_home_root()
    card = _find_node(root, "7342:2820")
    assert card is not None
    assert layout_fact_painted_dashboard_card_shell(card)
    assert not layout_fact_painted_multiline_field_shell(card)


def test_hairline_divider_skips_double_stroke_wrap() -> None:
    """Law: ZeroDimensionStrokeLaw — 1px dividers do not get expanded Positioned width."""
    from figma_flutter_agent.generator.layout.widgets import render_node_body

    root = _load_home_root()
    line = _find_node(root, "7342:2834")
    assert line is not None
    body = render_node_body(line, uses_svg=True)
    assert "Positioned(width: 2.0" not in body


def test_nav_active_substrate_uses_fixed_extent() -> None:
    """Law: NavActiveSubstrateInvariantLaw — active pill uses painted substrate extent."""
    from figma_flutter_agent.generator.layout.navigation.helpers import icon_nav_stateful_helpers

    helpers = icon_nav_stateful_helpers(node_id="test")
    build_tab = helpers.split("Widget _buildTab")[1]
    assert "width: widget.activeSubstrateWidth," in build_tab
    assert "height: widget.activeSubstrateHeight," in build_tab


def test_segment_tab_labels_centered_in_cells() -> None:
    """Law: segment_label_centered_in_cell — tab switcher centers labels in each segment."""
    from figma_flutter_agent.generator.layout.widgets.emit.tab_switcher import (
        emit_tab_switcher_stack_children,
    )

    host = CleanDesignTreeNode(
        id="1:tabs",
        name="Tabs",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=32.0),
        children=[
            CleanDesignTreeNode(
                id="1:a",
                name="A",
                type=NodeType.TEXT,
                text="Daily",
                sizing=Sizing(width=40.0, height=16.0),
            ),
            CleanDesignTreeNode(
                id="1:b",
                name="B",
                type=NodeType.TEXT,
                text="Monthly",
                sizing=Sizing(width=50.0, height=16.0),
            ),
        ],
    )
    pairs = [
        (child, f"Text('{child.text}')") for child in host.children if child.type == NodeType.TEXT
    ]
    emitted = emit_tab_switcher_stack_children(host, emitted_pairs=pairs)
    assert "Expanded(child: Center(child:" in emitted.replace("\n", "")


def test_home_replay_rejects_checkbox_and_field_regressions() -> None:
    """Law: orchestration replay — no checkbox badges or Food Last Week TextField."""
    from figma_flutter_agent.generator.layout import render_layout_file

    root = _load_home_root()
    screen_ir = _load_home_screen_ir()
    files = render_layout_file(
        root,
        feature_name="9_a_home_bottom_navigation_laws",
        uses_svg=True,
        screen_ir=screen_ir,
        responsive_enabled=True,
    )
    compact = "".join(files.values())
    salary_idx = compact.find("figma-7342_2861")
    if salary_idx >= 0:
        salary_window = compact[salary_idx : salary_idx + 600]
        assert "_GeneratedToggleCheckbox" not in salary_window
        assert "semanticsLabel: 'Salary'" not in salary_window
    assert "hintText: 'Food Last Week'" not in compact
