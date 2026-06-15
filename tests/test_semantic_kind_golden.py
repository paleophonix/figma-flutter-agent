"""Per-kind semantic vs geometric emit harness (EPIC 3.2)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.schemas import WidgetIrKind, WidgetIrNode
from tests.support.semantic_golden import emit_geometric_path, emit_semantic_path
from tests.support.semantics_trees import filled_button, weekday_chip_row

_MVP_FIXTURES = [
    (
        "button_filled",
        filled_button,
        "btn-filled",
        WidgetIrKind.BUTTON_FILLED,
        ("ElevatedButton", "CupertinoButton"),
    ),
    ("chip_choice", weekday_chip_row, "chip-row", WidgetIrKind.CHIP_CHOICE, ("ChoiceChip",)),
]


def _classified_root(clean):
    ir = default_screen_ir(clean)
    classified, _ = classify_screen_ir(
        ir,
        clean,
        confidence_threshold=0.8,
        grey_zone_min=0.5,
        authoritative_classifier=True,
        llm_gray_zone_enabled=False,
    )
    return stamp_fidelity_tiers(classified).root


@pytest.mark.parametrize(
    ("kind_name", "tree_factory", "figma_id", "expected_kind", "native_markers"),
    _MVP_FIXTURES,
)
def test_semantic_emit_uses_native_widget(
    kind_name: str,
    tree_factory,
    figma_id: str,
    expected_kind: WidgetIrKind,
    native_markers: tuple[str, ...],
) -> None:
    del kind_name
    clean = tree_factory()
    root_ir = _classified_root(clean)
    assert root_ir.kind == expected_kind
    target = _find_node(root_ir, figma_id) or root_ir
    semantic = emit_semantic_path(
        target, clean=clean if target is root_ir else _find_clean(clean, figma_id)
    )
    assert any(marker in semantic for marker in native_markers)


@pytest.mark.parametrize(
    ("kind_name", "tree_factory", "figma_id", "expected_kind", "native_markers"),
    _MVP_FIXTURES,
)
def test_semantic_differs_from_geometric_when_verified(
    kind_name: str,
    tree_factory,
    figma_id: str,
    expected_kind: WidgetIrKind,
    native_markers: tuple[str, ...],
) -> None:
    del kind_name, expected_kind, native_markers
    clean = tree_factory()
    root_ir = _classified_root(clean)
    target = _find_node(root_ir, figma_id) or root_ir
    clean_node = clean if target is root_ir else _find_clean(clean, figma_id)
    semantic = emit_semantic_path(target, clean=clean_node)
    geometric = emit_geometric_path(target, clean=clean_node)
    assert semantic != geometric


def _find_node(node: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if node.figma_id == figma_id:
        return node
    for child in node.children:
        found = _find_node(child, figma_id)
        if found is not None:
            return found
    return None


def _find_clean(node, figma_id: str):
    if node.id == figma_id:
        return node
    for child in node.children:
        found = _find_clean(child, figma_id)
        if found is not None:
            return found
    return node
