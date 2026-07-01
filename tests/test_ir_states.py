"""Screen IR states and adaptive rules."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.states import (
    apply_adaptive_rules_to_ir,
    apply_screen_ir_states_and_rules,
    derive_state_by_figma_id,
    infer_widget_state,
    sync_state_to_clean_variant,
)
from figma_flutter_agent.generator.ir.tree import default_screen_ir, index_clean_tree
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.llm.ir_payload import dump_screen_ir_blueprint
from figma_flutter_agent.schemas import (
    AdaptiveRule,
    AdaptiveRuleWhen,
    CleanDesignTreeNode,
    ComponentVariant,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
    WidgetIrRef,
    WidgetIrState,
)


def test_infer_widget_state_disabled() -> None:
    node = CleanDesignTreeNode(
        id="1:1",
        name="Btn",
        type=NodeType.BUTTON,
        variant=ComponentVariant(state="Disabled", variant_properties={"State": "Disabled"}),
    )
    assert infer_widget_state(node) == WidgetIrState.DISABLED


def test_derive_state_by_figma_id_includes_button() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:1",
                name="Btn",
                type=NodeType.BUTTON,
                variant=ComponentVariant(variant_properties={"State": "Disabled"}),
            ),
        ],
    )
    states = derive_state_by_figma_id(root)
    assert states["1:1"] == WidgetIrState.DISABLED


def test_sync_state_to_clean_variant() -> None:
    node = CleanDesignTreeNode(id="1:1", name="Btn", type=NodeType.BUTTON)
    sync_state_to_clean_variant(node, WidgetIrState.ERROR)
    assert node.variant is not None
    assert node.variant.state == "Error"


def test_adaptive_rule_merges_override() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        sizing={"width": 390, "height": 844},
        children=[
            CleanDesignTreeNode(
                id="1:1",
                name="Label",
                type=NodeType.TEXT,
                text="Hello",
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:0",
            kind=WidgetIrKind.STACK,
            children=[WidgetIrNode(figma_id="1:1", kind=WidgetIrKind.TEXT)],
        ),
        adaptive_rules=[
            AdaptiveRule(
                figma_id="1:1",
                when=AdaptiveRuleWhen(min_viewport_width=0),
                overrides=WidgetIrOverrides(text="Patched"),
            ),
        ],
    )
    tree_by_id = index_clean_tree(root)
    apply_adaptive_rules_to_ir(screen_ir, tree_by_id=tree_by_id, viewport_width=390.0)
    text_ir = screen_ir.root.children[0]
    assert text_ir.overrides is not None
    assert text_ir.overrides.text == "Patched"


def test_apply_screen_ir_states_and_rules_syncs_variant() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:1",
                name="Btn",
                type=NodeType.BUTTON,
                variant=ComponentVariant(variant_properties={"State": "Disabled"}),
            ),
        ],
    )
    screen_ir = default_screen_ir(root)
    apply_screen_ir_states_and_rules(screen_ir, root)
    assert screen_ir.state_by_figma_id["1:1"] == WidgetIrState.DISABLED
    assert root.children[0].variant is not None
    assert root.children[0].variant.state == "Disabled"


def test_dump_screen_ir_blueprint_includes_states() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:1",
                name="Btn",
                type=NodeType.BUTTON,
                variant=ComponentVariant(variant_properties={"State": "Disabled"}),
            ),
        ],
    )
    blueprint = dump_screen_ir_blueprint(root)
    assert blueprint["stateByFigmaId"]["1:1"] == "disabled"
    assert blueprint["adaptiveRules"] == []


def test_validate_prunes_unknown_adaptive_rule_figma_id() -> None:
    root = CleanDesignTreeNode(id="1:0", name="Screen", type=NodeType.STACK)
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="1:0"),
        adaptive_rules=[
            AdaptiveRule(
                figma_id="9:9",
                when=AdaptiveRuleWhen(),
            ),
        ],
    )
    validate_screen_ir(screen_ir, root, apply_guards=False)
    assert screen_ir.adaptive_rules == []


def test_validate_prunes_adaptive_rule_missing_from_ir_graph() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(id="281:14438", name="Chip", type=NodeType.BUTTON),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="1:0", kind=WidgetIrKind.STACK),
        adaptive_rules=[
            AdaptiveRule(
                figma_id="281:14438",
                when=AdaptiveRuleWhen(min_viewport_width=0),
            ),
        ],
    )
    validate_screen_ir(screen_ir, root, apply_guards=False)
    assert screen_ir.adaptive_rules == []


def test_validate_downgrades_orphan_extracted_widget_ref() -> None:
    root = CleanDesignTreeNode(
        id="1:0",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="281:16143",
                name="OrderCardActionButton",
                type=NodeType.BUTTON,
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:0",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="281:16143",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="OrderCardActionButton"),
                ),
            ],
        ),
    )
    validate_screen_ir(
        screen_ir,
        root,
        extracted_widget_names=frozenset({"OtherWidget"}),
        declared_extracted_widget_names=frozenset(),
        apply_guards=False,
    )
    button_ir = screen_ir.root.children[0]
    assert button_ir.kind == WidgetIrKind.EXTRACTED
    assert button_ir.ref is not None
    assert button_ir.ref.widget_name == "OrderCardActionButton"
