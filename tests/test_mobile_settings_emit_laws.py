"""Emit laws exercised by the mobile_settings screen regressions."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.extracted import emit_extracted_widget_code_from_ir
from figma_flutter_agent.generator.ir.extracted_paint import (
    extracted_widget_subtree_conservation_needs_rematerialization,
)
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.flex_policy.stack import stack_flow_column_child_sort_key
from figma_flutter_agent.generator.layout.navigation.helpers import bottom_nav_stateful_helpers
from figma_flutter_agent.generator.layout.widget_roots import (
    finalize_extracted_widget_body,
    validate_widget_build_has_no_parent_data_root,
)
from figma_flutter_agent.generator.widget_extraction.collect import collect_widget_specs
from figma_flutter_agent.generator.widget_extraction.enrich import apply_widget_enrich_response
from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets
from figma_flutter_agent.parser.interaction.icons import layout_fact_occluding_icon_fill_plate
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement
from figma_flutter_agent.schemas.ir import WidgetIrNode
from figma_flutter_agent.schemas.reusable_candidates import WidgetEnrichResponse

_FIXTURE = Path(".debug/screen/limbo/mobile_settings/processed.json")
_ENRICH = Path(".debug/screen/limbo/mobile_settings/widget_enrich.json")

_DIVIDER_STACK_BODY = (
    "Stack(clipBehavior: Clip.none, children: ["
    "Positioned(left: 0.0, bottom: 0.0, width: 343.0, height: 0.5, "
    "key: ValueKey('figma-I272_9316_126_1617'), "
    "child: Semantics(label: 'Divider', "
    "child: SvgPicture.asset('assets/icons/divider_I272_9316;126_1617.svg', "
    "width: 343.0, height: 1.0, fit: BoxFit.fitWidth)))])"
)


def test_single_positioned_child_stack_body_is_unwrapped() -> None:
    """A Stack whose only child is a Positioned unwraps to that child.

    Regression: SettingsDividerWidget returned a bare Stack of a single
    Positioned. In an unbounded-height Column the Stack fails ``size.isFinite``
    (``A Stack requires bounded constraints``) and the whole screen renders blank.
    """
    out = finalize_extracted_widget_body(_DIVIDER_STACK_BODY)
    assert not out.startswith("Stack("), out[:40]
    assert not out.startswith("Positioned("), out[:40]
    # The lone Positioned's child survives (bounded widget, safe in any host).
    assert out.startswith("Semantics(") or out.startswith("SvgPicture.asset(")
    assert "SvgPicture.asset(" in out


def test_multi_positioned_child_stack_body_kept() -> None:
    """A Stack with multiple positioned children is not unwrapped (overlapping)."""
    body = (
        "Stack(clipBehavior: Clip.none, children: ["
        "Positioned(left: 0.0, top: 0.0, child: Text('a')), "
        "Positioned(left: 5.0, top: 5.0, child: Text('b'))])"
    )
    out = finalize_extracted_widget_body(body)
    assert out.startswith("Stack(")


def test_unwrapped_divider_body_passes_parent_data_gate() -> None:
    """After unwrap the widget file must not trip the Positioned-root gate."""
    body = finalize_extracted_widget_body(_DIVIDER_STACK_BODY)
    source = (
        "class SettingsDividerWidget extends StatelessWidget {\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        f"    return {body};\n"
        "  }\n"
        "}\n"
    )
    assert validate_widget_build_has_no_parent_data_root(source) == []


def _load_root() -> CleanDesignTreeNode:
    if not _FIXTURE.is_file():
        pytest.skip("mobile_settings debug dumps not available")
    processed = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(processed["cleanTree"])


def _cluster_summary(root: CleanDesignTreeNode) -> dict[str, int]:
    counts: Counter[str] = Counter()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            counts[node.cluster_id] += 1
        for child in node.children:
            walk(child)

    walk(root)
    return dict(counts)


def test_settings_divider_cluster_widget_emits_bounded_root() -> None:
    """Integration: cluster render must not return a bare unbounded Stack root."""
    if not _ENRICH.is_file():
        pytest.skip("mobile_settings widget_enrich.json not available")
    root = _load_root()
    config = WidgetExtractionConfig()
    specs = collect_widget_specs(
        root,
        cluster_summary=_cluster_summary(root),
        config=config,
        llm_candidates=None,
    )
    enrich_raw = json.loads(_ENRICH.read_text(encoding="utf-8"))
    enrich = WidgetEnrichResponse.model_validate(enrich_raw["response"])
    specs = apply_widget_enrich_response(specs, enrich, widget_suffix="Widget")
    result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[root])
    divider = result.files["lib/widgets/settings_divider_widget.dart"]
    assert "return Stack(" not in divider
    assert "SvgPicture.asset(" in divider


def test_bottom_viewport_chrome_sorts_after_body_tier() -> None:
    """SystemChromeDockingLaw: home indicator uses trailing flow-column tier."""
    home = CleanDesignTreeNode(
        id="home",
        name="iOS / Home Indicator",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=34.0),
        stack_placement=StackPlacement(vertical="BOTTOM", height=34.0),
        children=[],
    )
    body = CleanDesignTreeNode(
        id="body",
        name="Profile info",
        type=NodeType.COLUMN,
        sizing=Sizing(width=375.0, height=400.0),
        children=[],
    )
    assert stack_flow_column_child_sort_key(home)[0] > stack_flow_column_child_sort_key(body)[0]


def test_chevron_button_fill_plate_is_occluding_on_button_host() -> None:
    """CompositeIconSilhouetteLaw: BUTTON chevron hosts veto full-bounds Fill plates."""
    root = _load_root()
    button = None
    stack = [root]
    while stack:
        node = stack.pop()
        if node.id == "I272:9260;126:1367":
            button = node
            break
        stack.extend(node.children)
    assert button is not None
    fill = next(child for child in button.children if child.name == "Fill")
    assert layout_fact_occluding_icon_fill_plate(fill, parent=button)


def test_chevron_cluster_widget_omits_occluding_fill_ink() -> None:
    """ChevronButtonWidget must not paint occluding Fill as Ink decoration."""
    if not _ENRICH.is_file():
        pytest.skip("mobile_settings widget_enrich.json not available")
    root = _load_root()
    specs = _collect_enriched_specs(root)
    result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[root])
    chevron = result.files["lib/widgets/chevron_button_widget.dart"]
    assert "0xFF8F9098" not in chevron
    assert "Ink(decoration: BoxDecoration(color:" not in chevron


def _collect_enriched_specs(root: CleanDesignTreeNode):
    config = WidgetExtractionConfig()
    specs = collect_widget_specs(
        root,
        cluster_summary=_cluster_summary(root),
        config=config,
        llm_candidates=None,
    )
    enrich_raw = json.loads(_ENRICH.read_text(encoding="utf-8"))
    enrich = WidgetEnrichResponse.model_validate(enrich_raw["response"])
    return apply_widget_enrich_response(specs, enrich, widget_suffix="Widget")


def test_avatar_extracted_widget_materializes_full_subtree() -> None:
    """LAW-WIDGETIR-CONSERVE: Avatar extracted widget keeps profile plate and edit overlay."""
    root = _load_root()
    specs = _collect_enriched_specs(root)
    cluster_result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[root])
    pre = json.loads(
        Path(".debug/screen/limbo/mobile_settings/pre_emit.json").read_text(encoding="utf-8")
    )
    widget_ir = WidgetIrNode.model_validate(pre["extractedWidgets"][0]["widgetIr"])
    ctx = IrEmitContext(
        uses_svg=True,
        cluster_classes=cluster_result.cluster_classes,
        responsive_enabled=True,
    )
    code = emit_extracted_widget_code_from_ir(
        widget_ir,
        clean_tree=root,
        widget_name="ProfileAvatarWidget",
        ctx=ctx,
    )
    assert "81.5" in code
    assert "80.0" in code
    assert "272_9231" in code
    assert "272_9625" in code


def test_extracted_widget_subtree_conservation_detects_edit_only_cache() -> None:
    """Cached edit-only avatar body must trigger rematerialization against full host."""
    root = _load_root()
    avatar_host = None
    stack = [root]
    while stack:
        node = stack.pop()
        if node.id == "272:9638":
            avatar_host = node
            break
        stack.extend(node.children)
    assert avatar_host is not None
    stale = (
        "class AvatarWidget extends StatelessWidget {\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        "    return SizedBox(width: 24.0, height: 24.0, child: Text('edit'));\n"
        "  }\n"
        "}\n"
    )
    assert extracted_widget_subtree_conservation_needs_rematerialization(avatar_host, stale)


def test_flat_bottom_nav_helper_suppresses_material_elevation() -> None:
    """FigmaChromeElevationMatchLaw: generated chrome uses zero elevation."""
    helpers = bottom_nav_stateful_helpers(theme_variant="material_3", node_id="272:9115")
    assert "elevation: 0" in helpers
    assert "backgroundColor: Colors.white" in helpers


def test_mobile_settings_layout_places_home_indicator_after_profile_block() -> None:
    """Regression: home indicator must not precede avatar/profile content in flow column."""
    if not _ENRICH.is_file():
        pytest.skip("mobile_settings widget_enrich.json not available")
    root = _load_root()
    specs = _collect_enriched_specs(root)
    cluster_result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[root])
    layout = render_layout_file(
        root,
        feature_name="mobile_settings",
        cluster_classes=cluster_result.cluster_classes,
        uses_svg=True,
        theme_variant="material",
        responsive_enabled=True,
    )["lib/generated/mobile_settings_layout.dart"]
    home_idx = layout.find("figma-I272_9113_126_2469")
    avatar_idx = layout.find("ProfileAvatarWidget")
    if avatar_idx < 0:
        avatar_idx = layout.find("AvatarWidget")
    assert home_idx > 0 and avatar_idx > 0
    assert avatar_idx < home_idx
