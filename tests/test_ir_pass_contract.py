"""Contract gate for registered IR passes (RAR program 01, LAW-PASS-CONTRACT).

Every registered ``Pass`` must declare a non-empty ``mutates`` / ``preserves`` set drawn
from the known contract vocabulary. A new pass added without a contract entry fails here,
satisfying готовности criterion 3 of ``refactor/01_compiler-semantics-ir-contract.md``.

Also pins field-preservation laws for arrow A1 (``merge`` / ``_apply_ir_overrides``):
an override changes only its declared field and never drops geometry or children.
"""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.contract import _CLEAN_FIELD_TOKENS
from figma_flutter_agent.generator.ir.passes.protocol import Pass
from figma_flutter_agent.generator.ir.passes.registry import WAVE_1_IR_PASSES
from figma_flutter_agent.generator.ir.passes.semantic import SEMANTIC_PASSES
from figma_flutter_agent.generator.ir.tree import _apply_ir_overrides
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    WidgetIrNode,
    WidgetIrOverrides,
)

_ALL_PASSES: tuple[Pass, ...] = (*WAVE_1_IR_PASSES, *SEMANTIC_PASSES)

# Clean-tree field tokens the mutation validator understands, plus the graph defaults.
_CLEAN_MUTATE_TOKENS = {token for _field, token in _CLEAN_FIELD_TOKENS} | {
    "children",
    "screen_ir",
    "clean_tree",
}
# IR-side tokens are declared as ``screen_ir.<attribute>``.
_IR_FIELD_NAMES = set(WidgetIrNode.model_fields.keys())
_ALLOWED_PRESERVE_TOKENS = {
    "node_multiset",
    "stack_paint_order",
    "graph_sync",
    "kind",
    "style",
    "geometry",
}


def _mutate_token_is_known(token: str) -> bool:
    if token in _CLEAN_MUTATE_TOKENS:
        return True
    if token.startswith("screen_ir."):
        return token.split(".", 1)[1] in _IR_FIELD_NAMES
    return False


def test_every_registered_pass_declares_a_contract() -> None:
    """LAW-PASS-CONTRACT: no registered pass may omit its mutate/preserve contract."""
    for registered in _ALL_PASSES:
        assert registered.mutates, f"pass {registered.name!r} declares no mutates"
        assert registered.preserves, f"pass {registered.name!r} declares no preserves"


def test_pass_mutate_tokens_are_in_vocabulary() -> None:
    for registered in _ALL_PASSES:
        unknown = {token for token in registered.mutates if not _mutate_token_is_known(token)}
        assert not unknown, f"pass {registered.name!r} declares unknown mutate tokens {unknown}"


def test_pass_preserve_tokens_are_in_vocabulary() -> None:
    for registered in _ALL_PASSES:
        unknown = registered.preserves - _ALLOWED_PRESERVE_TOKENS
        assert not unknown, f"pass {registered.name!r} declares unknown preserve tokens {unknown}"


def _styled_container() -> CleanDesignTreeNode:
    node = CleanDesignTreeNode(
        id="card",
        name="Card",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=240.0, height=120.0),
        children=[
            CleanDesignTreeNode(id="title", name="Title", type=NodeType.TEXT, text="Hi"),
            CleanDesignTreeNode(id="body", name="Body", type=NodeType.TEXT, text="World"),
        ],
    )
    return node.model_copy(
        update={"style": node.style.model_copy(update={"background_color": "#222222"})},
    )


def test_text_override_preserves_sizing_children_and_untouched_style() -> None:
    """A1 field-preservation: overriding text drops neither geometry nor siblings."""
    node = _styled_container()
    result = _apply_ir_overrides(node, WidgetIrOverrides(text="Changed"))

    assert result.text == "Changed"
    assert result.sizing == node.sizing
    assert [child.id for child in result.children] == [child.id for child in node.children]
    assert result.style.background_color == "#222222"


def test_override_none_is_identity() -> None:
    """A1 idempotence: no overrides means the merged node is the same object."""
    node = _styled_container()
    assert _apply_ir_overrides(node, None) is node
