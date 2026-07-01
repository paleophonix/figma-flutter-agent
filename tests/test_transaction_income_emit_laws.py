"""Regression tests for transaction-income icon badge and table-column emit laws."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.extracted import (
    _extracted_widget_needs_decoration_rematerialization,
    _preserve_extracted_widget_decoration_shell,
    emit_extracted_widget_code_from_ir,
)
from figma_flutter_agent.generator.layout.flex_policy.stack import layout_fact_icon_badge_stack
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.position import (
    _ensure_positioned_stack_bounds,
    positioned_text_prefers_explicit_width_pins,
)
from figma_flutter_agent.generator.layout.widgets.text import _positioned_fields
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _calendar_badge_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="7043:3387",
        name="Calender",
        type=NodeType.STACK,
        sizing=Sizing(width=32.3, height=30.0),
        children=[
            CleanDesignTreeNode(
                id="I7043:3387;7043:3015",
                name="Rectangle 269",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=32.3, height=30.0),
                style=NodeStyle(background_color="0xFF00D09E", border_radius=12.5),
            ),
            CleanDesignTreeNode(
                id="I7043:3387;7043:3017",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_calendar.svg",
                sizing=Sizing(width=17.9, height=15.8),
                stack_placement=StackPlacement(
                    left=7.4,
                    top=6.8,
                    width=17.9,
                    height=15.8,
                ),
            ),
        ],
    )


def _salary_icon_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="7110:1045",
        name="Icon Salary",
        type=NodeType.STACK,
        cluster_id="component_7102_2848",
        sizing=Sizing(width=57.0, height=53.0),
        children=[
            CleanDesignTreeNode(
                id="I7110:1045;7102:2847",
                name="Rectangle 150",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=57.0, height=53.0),
                style=NodeStyle(background_color="0xFF6DB6FE", border_radius=22.0),
            ),
            CleanDesignTreeNode(
                id="I7110:1045;7102:1277",
                name="Vector",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/vector_salary.svg",
                sizing=Sizing(width=26.0, height=23.5),
                stack_placement=StackPlacement(
                    left=16.0,
                    top=15.0,
                    width=26.0,
                    height=23.5,
                ),
            ),
        ],
    )


def _arrow_chip_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="I7110:3217;7110:3187",
        name="Group 395",
        type=NodeType.STACK,
        sizing=Sizing(width=25.0, height=25.0),
        children=[
            CleanDesignTreeNode(
                id="I7110:3217;7110:3188",
                name="Rectangle 31",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=25.0, height=25.0),
                style=NodeStyle(
                    border_radius=6.3,
                    border_width=2.08,
                    border_color="0xFFF1FFF3",
                    has_stroke=True,
                ),
            ),
            CleanDesignTreeNode(
                id="I7110:3217;7110:3189",
                name="Arrow 1",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/arrow_1.svg",
                sizing=Sizing(width=12.5, height=12.5),
                stack_placement=StackPlacement(
                    left=6.25,
                    top=6.25,
                    width=12.5,
                    height=12.5,
                ),
            ),
        ],
    )


def _monthly_category_text() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="7035:1284",
        name="Monthly",
        type=NodeType.TEXT,
        text="Monthly",
        sizing=Sizing(width=48.0, height=18.0),
        style=NodeStyle(font_size=12.0, font_weight="w400", text_align="LEFT"),
        stack_placement=StackPlacement(
            horizontal="CENTER",
            vertical="BOTTOM",
            left=191.0,
            top=426.0,
            right=143.0,
            bottom=488.0,
            width=48.0,
            height=18.0,
        ),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=239.0, y=426.0, width=48.0, height=18.0),
        ),
    )


def _amount_text() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="7035:1294",
        name="$120,00",
        type=NodeType.TEXT,
        text="$120,00",
        sizing=Sizing(width=56.0, height=23.0),
        style=NodeStyle(font_size=15.0, font_weight="w500", text_align="RIGHT"),
        stack_placement=StackPlacement(
            horizontal="CENTER",
            left=187.0,
            top=501.0,
            right=35.0,
            bottom=408.0,
            width=56.0,
            height=23.0,
        ),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=339.0, y=501.0, width=56.0, height=23.0),
        ),
    )


def test_icon_badge_stack_detects_salary_and_notification_glyph_hosts() -> None:
    salary = _salary_icon_stack()
    assert layout_fact_icon_badge_stack(salary)
    notification = CleanDesignTreeNode(
        id="7253:3639",
        name="Icon-Notification",
        type=NodeType.STACK,
        sizing=Sizing(width=30.0, height=30.0),
        style=NodeStyle(background_color="0xFFDFF7E2", border_radius=25.7),
        children=[
            CleanDesignTreeNode(
                id="I7253:3639;7043:3064",
                name="Vector",
                type=NodeType.STACK,
                sizing=Sizing(width=14.6, height=18.9),
                vector_asset_key="assets/icons/vector_bell.svg",
                children=[],
            )
        ],
    )
    assert layout_fact_icon_badge_stack(notification)


def test_icon_badge_stack_emits_substrate_and_intrinsic_glyph() -> None:
    badge = _calendar_badge_stack()
    emitted = render_node_body(badge, uses_svg=True, theme_variant="material_3")
    assert "BoxDecoration(" in emitted
    assert "Color(0xFF00D09E)" in emitted
    assert "width: 17.9" in emitted
    assert "SvgPicture" in emitted


def test_icon_badge_stack_emits_stroke_frame_for_summary_arrow_chip() -> None:
    chip = _arrow_chip_stack()
    assert layout_fact_icon_badge_stack(chip)
    emitted = render_node_body(chip, uses_svg=True, theme_variant="material_3")
    assert "BoxDecoration(" in emitted
    assert "Border.all" in emitted
    assert "width: 12.5" in emitted


def test_extracted_salary_widget_preserves_blue_substrate_shell() -> None:
    salary = _salary_icon_stack()
    wrapped = _preserve_extracted_widget_decoration_shell(
        salary,
        "SvgPicture.asset('assets/icons/vector_salary.svg', width: 26.0, height: 23.5, fit: BoxFit.contain)",
    )
    assert "Color(0xFF6DB6FE)" in wrapped
    assert "width: 57.0" in wrapped
    assert "width: 26.0" in wrapped


def test_extracted_widget_missing_shell_triggers_rematerialization() -> None:
    salary = _salary_icon_stack()
    bare = (
        "class IconSalaryWidget extends StatelessWidget {"
        "@override Widget build(BuildContext context) {"
        "return SvgPicture.asset('assets/icons/x.svg', width: 57.0, height: 53.0);"
        "}}"
    )
    assert _extracted_widget_needs_decoration_rematerialization(salary, bare)


def test_extracted_salary_widget_with_cluster_classes_preserves_substrate() -> None:
    """Emit with cluster_classes must not self-delegate and must keep blue badge shell."""
    root = _salary_icon_stack()
    widget_ir = WidgetIrNode(
        figma_id="7110:1045",
        kind=WidgetIrKind.AUTO,
        children=[
            WidgetIrNode(figma_id="I7110:1045;7102:2847", kind=WidgetIrKind.AUTO),
            WidgetIrNode(figma_id="I7110:1045;7102:1277", kind=WidgetIrKind.AUTO),
        ],
    )
    ctx = IrEmitContext(
        uses_svg=True,
        responsive_enabled=False,
        is_layout_root=False,
        cluster_classes={"component_7102_2848": "IconSalaryWidget"},
    )
    code = emit_extracted_widget_code_from_ir(
        widget_ir,
        clean_tree=root,
        widget_name="IconSalaryWidget",
        ctx=ctx,
    )
    build = code.split("Widget build", 1)[1]
    assert "IconSalaryWidget(" not in build.replace("const IconSalaryWidget({super.key})", "")
    assert "0xFF6DB6FE" in code
    assert "SvgPicture" in code
    assert "width: 26.0" in code
    assert "width: 57.0, height: 53.0, fit: BoxFit.fill" not in code


def test_materialize_refreshes_icon_badge_with_plate_sized_glyph_cache() -> None:
    from figma_flutter_agent.generator.ir.extracted import materialize_extracted_widgets
    from figma_flutter_agent.schemas import ExtractedWidget

    salary = _salary_icon_stack()
    screen = CleanDesignTreeNode(
        id="7035:1262",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=430.0, height=932.0),
        children=[salary],
    )
    widget_ir = WidgetIrNode(
        figma_id="7110:1045",
        kind=WidgetIrKind.AUTO,
        children=[
            WidgetIrNode(figma_id="I7110:1045;7102:2847", kind=WidgetIrKind.AUTO),
            WidgetIrNode(figma_id="I7110:1045;7102:1277", kind=WidgetIrKind.AUTO),
        ],
    )
    stale = (
        "class IconSalaryWidget extends StatelessWidget {"
        "const IconSalaryWidget({super.key});"
        "@override Widget build(BuildContext context) {"
        "return Container(width: 57.0, height: 53.0, decoration: BoxDecoration("
        "color: Color(0xFF6DB6FE), borderRadius: BorderRadius.circular(22.0)), "
        "child: Center(child: SvgPicture.asset('assets/icons/x.svg', "
        "width: 57.0, height: 53.0, fit: BoxFit.fill)));"
        "}}"
    )
    widgets = [
        ExtractedWidget(
            widget_name="IconSalaryWidget",
            widget_ir=widget_ir,
            code=stale,
        )
    ]
    ctx = IrEmitContext(uses_svg=True, responsive_enabled=False, is_layout_root=False)
    refreshed = materialize_extracted_widgets(
        widgets,
        clean_tree=screen,
        ctx=ctx,
        prefer_existing_code=True,
    )[0].resolved_code()
    assert refreshed is not None
    assert "width: 26.0" in refreshed
    assert "width: 57.0, height: 53.0, fit: BoxFit.fill" not in refreshed


def test_subtree_salary_widget_body_inlines_cluster_content_not_self() -> None:
    from figma_flutter_agent.generator.subtree.render import _render_subtree_widget_body

    root = _salary_icon_stack()
    body = _render_subtree_widget_body(
        root,
        class_name="IconSalaryWidget",
        uses_svg=True,
        cluster_classes={"component_7102_2848": "IconSalaryWidget"},
    )
    assert "IconSalaryWidget(" not in body
    assert "0xFF6DB6FE" in body
    assert "SvgPicture" in body


def test_recursion_gate_catches_wrapped_self_reference() -> None:
    from figma_flutter_agent.generator.dart.static_contract_gates import (
        find_extracted_widget_empty_or_recursive_shells,
    )

    planned = {
        "lib/widgets/icon_salary_widget.dart": """
import 'package:flutter/material.dart';
class IconSalaryWidget extends StatelessWidget {
  const IconSalaryWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(child: const IconSalaryWidget());
  }
}
""",
    }
    violations = find_extracted_widget_empty_or_recursive_shells(planned)
    assert violations
    assert "icon_salary_widget.dart" in violations[0]


def test_identical_component_family_compact_icons_emit_one_subtree_spec() -> None:
    from figma_flutter_agent.generator.subtree.spec import collect_subtree_widget_specs

    def salary_instance(node_id: str) -> CleanDesignTreeNode:
        return CleanDesignTreeNode(
            id=node_id,
            name="Icon Salary",
            type=NodeType.STACK,
            component_ref="7102:2848",
            sizing=Sizing(width=57.0, height=53.0),
            stack_placement=StackPlacement(left=37.0, top=100.0, width=57.0, height=53.0),
            children=[
                CleanDesignTreeNode(
                    id=f"I{node_id.replace(':', '_')};7102:2847",
                    name="Rectangle 150",
                    type=NodeType.CONTAINER,
                    sizing=Sizing(width=57.0, height=53.0),
                    style=NodeStyle(background_color="0xFF6DB6FE", border_radius=22.0),
                ),
                CleanDesignTreeNode(
                    id=f"I{node_id.replace(':', '_')};7102:1277",
                    name="Vector",
                    type=NodeType.VECTOR,
                    vector_asset_key="assets/icons/vector.svg",
                    sizing=Sizing(width=26.0, height=23.5),
                ),
                CleanDesignTreeNode(
                    id=f"I{node_id.replace(':', '_')};7102:1278",
                    name="Vector 2",
                    type=NodeType.VECTOR,
                    vector_asset_key="assets/icons/vector2.svg",
                    sizing=Sizing(width=4.0, height=4.0),
                ),
            ],
        )

    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=430.0, height=932.0),
        children=[
            salary_instance("7110:1045"),
            salary_instance("7110:1051"),
            salary_instance("7110:1057"),
        ],
    )
    specs = collect_subtree_widget_specs(screen, widget_suffix="Widget")
    salary_specs = [spec for spec in specs if spec.class_name.startswith("IconSalary")]
    assert len(salary_specs) == 1


def test_collapse_numbered_widget_stem_aliases_rewrites_callsites() -> None:
    from figma_flutter_agent.generator.planned.reconcile.widget_prune import (
        collapse_numbered_widget_stem_aliases,
    )

    planned = {
        "lib/widgets/icon_salary_widget.dart": (
            "class IconSalaryWidget extends StatelessWidget {"
            "const IconSalaryWidget({super.key});"
            "Widget build(BuildContext c) => const SizedBox();"
            "}"
        ),
        "lib/widgets/icon_salary_widget2.dart": (
            "class IconSalaryWidget2 extends StatelessWidget {"
            "const IconSalaryWidget2({super.key});"
            "Widget build(BuildContext c) => const SizedBox();"
            "}"
        ),
        "lib/generated/screen_layout.dart": "child: const IconSalaryWidget2(),",
    }
    updated = collapse_numbered_widget_stem_aliases(planned)
    assert "lib/widgets/icon_salary_widget2.dart" not in updated
    assert "IconSalaryWidget2(" not in updated["lib/generated/screen_layout.dart"]
    assert "IconSalaryWidget(" in updated["lib/generated/screen_layout.dart"]


def test_bottom_chrome_not_inside_scroll_extent() -> None:
    """Static-mode fallback must not wrap the full artboard in an outer scroll host."""
    import json
    from pathlib import Path

    import pytest

    from figma_flutter_agent.generator.layout import render_layout_file
    from figma_flutter_agent.generator.normalize import normalize_clean_tree
    from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr

    debug_root = Path(".debug/screen/limbo/9_3_1_b_transaction_income")
    if not (debug_root / "processed.json").is_file():
        pytest.skip("transaction income debug bundle unavailable")
    proc = json.loads((debug_root / "processed.json").read_text(encoding="utf-8"))
    pre = json.loads((debug_root / "pre_emit.json").read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(proc["cleanTree"])
    screen_ir = ScreenIr.model_validate(pre["screenIr"])
    norm = normalize_clean_tree(root, screen_ir=screen_ir)
    layout = render_layout_file(
        norm,
        feature_name="9_3_1_b_transaction_income",
        uses_svg=True,
        screen_ir=screen_ir,
        de_archetype_pass=True,
        responsive_enabled=False,
    )["lib/generated/9_3_1_b_transaction_income_layout.dart"]
    bad_outer_scroll = (
        "Material(color: Colors.transparent, child: Align(alignment: Alignment.topLeft, "
        "child: SingleChildScrollView(child: SizedBox(width: 430.0, height: 932.0"
    )
    assert bad_outer_scroll not in layout
    assert "Alignment.bottomCenter" in layout
    assert "ClipRect(" in layout


def test_bottom_nav_is_terminal_paint_layer() -> None:
    """Bottom navigation must be the last painted stack child."""
    import json
    import re
    from pathlib import Path

    import pytest

    from figma_flutter_agent.generator.layout import render_layout_file
    from figma_flutter_agent.generator.normalize import normalize_clean_tree
    from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr

    debug_root = Path(".debug/screen/limbo/9_3_1_b_transaction_income")
    if not (debug_root / "processed.json").is_file():
        pytest.skip("transaction income debug bundle unavailable")
    proc = json.loads((debug_root / "processed.json").read_text(encoding="utf-8"))
    pre = json.loads((debug_root / "pre_emit.json").read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(proc["cleanTree"])
    screen_ir = ScreenIr.model_validate(pre["screenIr"])
    norm = normalize_clean_tree(root, screen_ir=screen_ir)
    layout = render_layout_file(
        norm,
        feature_name="9_3_1_b_transaction_income",
        uses_svg=True,
        screen_ir=screen_ir,
        de_archetype_pass=True,
        responsive_enabled=False,
    )["lib/generated/9_3_1_b_transaction_income_layout.dart"]
    keys = [match.group(1) for match in re.finditer(r"key: ValueKey\('figma-([^']+)'\)", layout)]
    assert "7420_7339" in keys
    nav_index = max(index for index, key in enumerate(keys) if key == "7420_7339")
    assert all(key != "7420_7339" for key in keys[nav_index + 1 :])


def test_icon_glyph_uses_intrinsic_bounds_not_plate() -> None:
    salary = _salary_icon_stack()
    emitted = render_node_body(salary, uses_svg=True, theme_variant="material_3")
    assert "width: 26.0" in emitted
    assert "width: 57.0, height: 53.0, fit: BoxFit.fill" not in emitted


def test_icon_badge_emits_plate_and_glyph() -> None:
    badge = _calendar_badge_stack()
    emitted = render_node_body(badge, uses_svg=True, theme_variant="material_3")
    assert "Color(0xFF00D09E)" in emitted
    assert "width: 17.9" in emitted
    assert "SvgPicture" in emitted


def test_wizard_preview_viewport_pins_bottom_chrome_without_outer_scroll() -> None:
    from figma_flutter_agent.generator.layout.common import (
        artboard_static_wizard_preview,
        wrap_artboard_preview_layout_builder,
    )

    preview = artboard_static_wizard_preview(
        scroll_child="child",
        viewport_pin_bottom_chrome=True,
    )
    assert "SingleChildScrollView(" not in preview
    assert "Alignment.bottomCenter" in preview
    wrapped = wrap_artboard_preview_layout_builder(
        preview_child="SizedBox(width: _artboardPreviewWidth, height: _artboardPreviewHeight, child: child)",
        fallback="child",
        viewport_pin_bottom_chrome=True,
    )
    assert "viewport_pin_bottom_chrome" not in wrapped
    assert "Alignment.bottomCenter" in wrapped
    assert "SingleChildScrollView(" not in wrapped.split("if (_artboardCaptureMode)")[1]


def test_positioned_text_dual_pin_prefers_explicit_width_for_table_cells() -> None:
    monthly = _monthly_category_text()
    placement = monthly.stack_placement
    assert placement is not None
    assert positioned_text_prefers_explicit_width_pins(
        monthly,
        placement,
        parent_width=430.0,
        width=48.0,
    )
    fields = _positioned_fields(placement)
    _ensure_positioned_stack_bounds(
        fields,
        monthly,
        placement,
        parent_width=430.0,
        parent_height=932.0,
    )
    joined = ", ".join(fields)
    assert "left: 239.0" in joined
    assert "width: 48.0" in joined
    assert "right:" not in joined

    amount = _amount_text()
    amount_placement = amount.stack_placement
    assert amount_placement is not None
    fields_amount = _positioned_fields(amount_placement)
    _ensure_positioned_stack_bounds(
        fields_amount,
        amount,
        amount_placement,
        parent_width=430.0,
        parent_height=932.0,
    )
    joined_amount = ", ".join(fields_amount)
    assert "right: 35.0" in joined_amount
    assert "width: 56.0" in joined_amount
    assert "left: 187.0" not in joined_amount


def test_transaction_income_layout_emits_calendar_plate_and_salary_glyph() -> None:
    import json
    from pathlib import Path

    import pytest

    from figma_flutter_agent.generator.ir.extracted import emit_extracted_widget_code_from_ir
    from figma_flutter_agent.generator.ir.tree import index_clean_tree
    from figma_flutter_agent.generator.layout import render_layout_file
    from figma_flutter_agent.generator.normalize import normalize_clean_tree
    from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr, WidgetIrNode

    debug_root = Path(".debug/screen/limbo/9_3_1_b_transaction_income")
    if not (debug_root / "processed.json").is_file():
        pytest.skip("transaction income debug bundle unavailable")
    proc = json.loads((debug_root / "processed.json").read_text(encoding="utf-8"))
    pre = json.loads((debug_root / "pre_emit.json").read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(proc["cleanTree"])
    screen_ir = ScreenIr.model_validate(pre["screenIr"])
    norm = normalize_clean_tree(root, screen_ir=screen_ir)
    layout = render_layout_file(
        norm,
        feature_name="9_3_1_b_transaction_income",
        uses_svg=True,
        screen_ir=screen_ir,
        de_archetype_pass=True,
    )["lib/generated/9_3_1_b_transaction_income_layout.dart"]
    assert "figma-I7043_3387_7043_3015" in layout
    assert "Color(0xFF00D09E)" in layout
    salary_entry = next(
        widget for widget in pre["extractedWidgets"] if widget["widgetName"] == "IconSalaryWidget"
    )
    salary_node = index_clean_tree(norm)["7110:1045"]
    salary_code = emit_extracted_widget_code_from_ir(
        WidgetIrNode.model_validate(salary_entry["widgetIr"]),
        clean_tree=root,
        widget_name="IconSalaryWidget",
        ctx=IrEmitContext(uses_svg=True, responsive_enabled=False, is_layout_root=False),
    )
    assert "width: 26.0" in salary_code
    assert "width: 57.0, height: 53.0, fit: BoxFit.fill" not in salary_code
    assert salary_node.sizing.width == 57.0
