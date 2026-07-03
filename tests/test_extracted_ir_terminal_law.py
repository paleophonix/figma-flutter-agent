"""ExtractedRefTerminalLaw — screen IR extracted nodes are opaque leaves."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.presence import normalize_screen_ir_presence
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.generator.ir.validate.graph import (
    enforce_extracted_screen_ir_terminals,
    ensure_ir_direct_children_match_clean,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
)


def _composite_card_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="card:1",
                name="Card",
                type=NodeType.STACK,
                sizing=Sizing(width=327.0, height=141.0),
                children=[
                    CleanDesignTreeNode(
                        id="card:1:bg",
                        name="Background",
                        type=NodeType.CONTAINER,
                        sizing=Sizing(width=327.0, height=141.0),
                    ),
                    CleanDesignTreeNode(
                        id="card:1:row",
                        name="Row",
                        type=NodeType.ROW,
                        children=[
                            CleanDesignTreeNode(
                                id="card:1:icon",
                                name="Icon",
                                type=NodeType.VECTOR,
                                sizing=Sizing(width=20.0, height=20.0),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _extracted_screen_ir() -> ScreenIr:
    return ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[],
                    ref=WidgetIrRef(widget_name="GroupCardWidget"),
                ),
            ],
        ),
    )


def test_ensure_ir_direct_children_match_clean_skips_extracted_terminal() -> None:
    tree = _composite_card_tree()
    screen_ir = _extracted_screen_ir()
    inserted = ensure_ir_direct_children_match_clean(screen_ir, tree)
    assert inserted == 0
    assert screen_ir.root.children[0].children == []


def test_normalize_presence_keeps_valid_extracted_terminal() -> None:
    tree = _composite_card_tree()
    screen_ir = _extracted_screen_ir()
    normalized = normalize_screen_ir_presence(
        screen_ir,
        tree,
        extracted_widget_names=frozenset({"GroupCardWidget"}),
    )
    extracted = normalized.root.children[0]
    assert extracted.kind == WidgetIrKind.EXTRACTED
    assert extracted.ref is not None
    assert extracted.ref.widget_name == "GroupCardWidget"
    assert extracted.children == []


def test_validate_screen_ir_passes_after_graph_sync_for_extracted_card() -> None:
    tree = _composite_card_tree()
    screen_ir = _extracted_screen_ir()
    normalized = normalize_screen_ir_presence(
        screen_ir,
        tree,
        extracted_widget_names=frozenset({"GroupCardWidget"}),
    )
    validate_screen_ir(
        normalized,
        tree,
        extracted_widget_names=frozenset({"GroupCardWidget"}),
        declared_extracted_widget_names=frozenset({"GroupCardWidget"}),
        apply_guards=False,
        skip_presence_normalize=True,
    )


def test_invalid_extracted_ref_downgrades_and_receives_clean_children() -> None:
    from figma_flutter_agent.generator.ir.presence.sanitize import (
        sanitize_screen_ir_extracted_refs,
    )

    tree = _composite_card_tree()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[],
                    ref=WidgetIrRef(widget_name="MissingWidget"),
                ),
            ],
        ),
    )
    downgraded, _ = sanitize_screen_ir_extracted_refs(
        screen_ir,
        tree,
        extracted_widget_names=frozenset({"OtherWidget"}),
        canonical_extracted_widget_names=frozenset({"OtherWidget"}),
    )
    assert downgraded == 1
    card_ir = screen_ir.root.children[0]
    assert card_ir.kind != WidgetIrKind.EXTRACTED
    inserted = ensure_ir_direct_children_match_clean(screen_ir, tree)
    assert inserted > 0
    assert card_ir.children


def test_check_graph_sync_allows_extracted_terminal_with_clean_subtree() -> None:
    from figma_flutter_agent.generator.geometry.invariants.conservation import check_graph_sync

    tree = _composite_card_tree()
    screen_ir = _extracted_screen_ir()
    assert not check_graph_sync(screen_ir, tree)


def test_check_graph_sync_rejects_extracted_host_with_inline_children() -> None:
    from figma_flutter_agent.generator.geometry.invariants.conservation import check_graph_sync

    tree = _composite_card_tree()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[WidgetIrNode(figma_id="card:1:bg", kind=WidgetIrKind.AUTO)],
                    ref=WidgetIrRef(widget_name="GroupCardWidget"),
                ),
            ],
        ),
    )
    violations = check_graph_sync(screen_ir, tree)
    assert any(
        item.node_id == "card:1" and "inline IR children" in item.detail for item in violations
    )


def test_enforce_extracted_terminals_clears_zombie_children_before_validate() -> None:
    tree = _composite_card_tree()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[WidgetIrNode(figma_id="card:1:bg", kind=WidgetIrKind.AUTO)],
                    ref=WidgetIrRef(widget_name="GroupCardWidget"),
                ),
            ],
        ),
    )
    stripped = enforce_extracted_screen_ir_terminals(screen_ir.root)
    assert stripped == 1
    assert screen_ir.root.children[0].children == []
    validate_screen_ir(
        screen_ir,
        tree,
        extracted_widget_names=frozenset({"GroupCardWidget"}),
        declared_extracted_widget_names=frozenset({"GroupCardWidget"}),
        apply_guards=False,
        skip_presence_normalize=True,
    )
