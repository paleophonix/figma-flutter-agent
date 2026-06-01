"""Tests for visual refine context helpers."""

from __future__ import annotations

from figma_flutter_agent.llm.refine_context import (
    audit_interaction_handlers,
    build_asset_warnings,
    build_canvas_size,
    build_foreground_layout_anchors,
    build_interactive_inventory,
    resolve_refine_focus,
)
from figma_flutter_agent.llm.repair import build_visual_refine_user_payload
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
    Sizing,
    StackPlacement,
)
from figma_flutter_agent.validation.pixeldiff import DiffBandRegion


def test_resolve_refine_focus_sequence() -> None:
    assert resolve_refine_focus(attempt=1, max_attempts=4) == "interaction"
    assert resolve_refine_focus(attempt=2, max_attempts=4) == "layout_spacing"
    assert resolve_refine_focus(attempt=3, max_attempts=4) == "typography_color"
    assert resolve_refine_focus(attempt=4, max_attempts=4) == "pixel_polish"


def test_build_interactive_inventory_collects_buttons_and_scroll() -> None:
    tree = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.CONTAINER,
        children=[
            CleanDesignTreeNode(
                id="2:1",
                name="Play",
                type=NodeType.BUTTON,
                text="Play",
            ),
            CleanDesignTreeNode(
                id="2:2",
                name="Tracks",
                type=NodeType.GRID,
                scroll_axis="vertical",
            ),
        ],
    )
    inventory = build_interactive_inventory(tree)
    assert len(inventory) == 2
    assert inventory[0]["type"] == "BUTTON"
    assert inventory[0]["labelText"] == "Play"
    assert inventory[1]["scrollAxis"] == "vertical"


def test_audit_interaction_handlers_flags_missing_callbacks() -> None:
    inventory = [
        {"nodeId": "2:1", "name": "Play", "type": "BUTTON", "labelText": "Play"},
    ]
    generation = FlutterGenerationResponse(
        screen_code="class DemoScreen extends StatelessWidget { @override Widget build(BuildContext c) => Text('Play'); }"
    )
    audit = audit_interaction_handlers(inventory, generation)
    assert audit["passedInteractionAudit"] is False
    assert audit["missingHandlers"]


def test_audit_interaction_handlers_passes_when_handlers_present() -> None:
    inventory = [
        {"nodeId": "2:1", "name": "Play", "type": "BUTTON", "labelText": "Play"},
    ]
    generation = FlutterGenerationResponse(
        screen_code="FilledButton(onPressed: () { // <custom-code>\n// </custom-code>\n}, child: Text('Play'))"
    )
    audit = audit_interaction_handlers(inventory, generation)
    assert audit["passedInteractionAudit"] is True


def test_build_canvas_size_from_root_frame() -> None:
    tree = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=390, height=844),
    )
    assert build_canvas_size(tree) == {"width": 390, "height": 844}


def test_build_asset_warnings_for_svg_filter_nodes() -> None:
    tree = CleanDesignTreeNode(
        id="1:1",
        name="Icon",
        type=NodeType.CONTAINER,
        vector_svg_has_filter=True,
        vector_asset_key="icons/play",
    )
    warnings = build_asset_warnings(clean_tree=tree, asset_manifest=[])
    assert warnings
    assert "SVG filter" in warnings[0]


def test_build_foreground_layout_anchors_skips_decorative_vectors() -> None:
    tree = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414, height=896),
        children=[
            CleanDesignTreeNode(
                id="2:1",
                name="Blur",
                type=NodeType.VECTOR,
                vector_asset_key="assets/icons/blob.svg",
            ),
            CleanDesignTreeNode(
                id="2:2",
                name="Title block",
                type=NodeType.CONTAINER,
                stack_placement=StackPlacement(left=75, top=392, width=264, height=67),
                children=[
                    CleanDesignTreeNode(
                        id="2:3",
                        name="Title",
                        type=NodeType.TEXT,
                        text="Focus Attention",
                    ),
                ],
            ),
        ],
    )
    anchors = build_foreground_layout_anchors(tree)
    assert len(anchors) == 1
    assert anchors[0]["top"] == 392
    assert anchors[0]["name"] == "Title block"


def test_build_visual_refine_user_payload_includes_layout_anchors_for_stack() -> None:
    generation = FlutterGenerationResponse(screen_code="class DemoScreen {}")
    stack_root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414, height=896),
        children=[
            CleanDesignTreeNode(
                id="2:1",
                name="Controls",
                type=NodeType.CONTAINER,
                stack_placement=StackPlacement(left=20, top=528, width=374, height=201),
            ),
        ],
    )
    from figma_flutter_agent.llm.payload_format import parse_labeled_user_payload

    payload = parse_labeled_user_payload(
        build_visual_refine_user_payload(
            feature_name="demo",
            clean_tree=stack_root,
            tokens=DesignTokens(),
            asset_manifest=[],
            current_generation=generation,
            changed_ratio=0.12,
            threshold=0.08,
            refine_attempt=2,
            max_refine_attempts=3,
            previous_changed_ratio=0.18,
            refine_focus="layout_spacing",
            diff_bands=(DiffBandRegion(name="top", changed_ratio=0.2, y_start=0, y_end=100),),
            interactive_inventory=[{"nodeId": "2:1", "type": "BUTTON"}],
            handler_audit={"passedInteractionAudit": False},
            canvas_size={"width": 390, "height": 844},
            asset_warnings=["SVG filter unsupported"],
        )
    )
    assert payload["refineFocus"] == "layout_spacing"
    assert payload["refineAttempt"] == 2
    assert payload["previousChangedRatio"] == 0.18
    assert payload["attachedImages"][0]["role"] == "figma_reference"
    assert payload["attachedImages"][1]["role"] == "flutter_render"
    assert payload["layoutAnchors"][0]["top"] == 528
    assert payload["visualDiff"]["diffRegions"][0]["name"] == "top"
    assert payload["interactiveInventory"]
    assert payload["handlerAudit"]["passedInteractionAudit"] is False
    assert payload["canvasSize"]["width"] == 390
    assert payload["assetWarnings"]
