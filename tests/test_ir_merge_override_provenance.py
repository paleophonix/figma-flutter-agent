"""LAW-A1-OVERRIDE-PROV: IR overrides must record provenance for fact mutations."""

from __future__ import annotations

from figma_flutter_agent.debug.provenance import ProvenanceRecorder
from figma_flutter_agent.generator.ir.tree import _apply_ir_overrides, merge_ir_node
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
)


def _activate_recorder(monkeypatch) -> ProvenanceRecorder:
    recorder = ProvenanceRecorder(feature_name="override-prov")
    monkeypatch.setattr(
        "figma_flutter_agent.debug.provenance.get_provenance_recorder",
        lambda: recorder,
    )
    return recorder


def _text_node(node_id: str = "text-1", *, text: str = "Hello") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Label",
        type=NodeType.TEXT,
        sizing=Sizing(width=100.0, height=20.0),
        text=text,
    )


def test_text_override_records_mutation(monkeypatch) -> None:
    recorder = _activate_recorder(monkeypatch)
    node = _text_node()
    result = _apply_ir_overrides(node, WidgetIrOverrides(text="Changed"))
    assert result.text == "Changed"
    assert len(recorder.mutations) == 1
    mutation = recorder.mutations[0]
    assert mutation.field == "text"
    assert mutation.old == "Hello"
    assert mutation.new == "Changed"
    assert mutation.checkpoint == "A1_merge"
    assert mutation.transform == "ir_override"


def test_font_size_override_records_mutation(monkeypatch) -> None:
    recorder = _activate_recorder(monkeypatch)
    node = _text_node()
    result = _apply_ir_overrides(node, WidgetIrOverrides(font_size=16.0))
    assert result.style.font_size == 16.0
    assert len(recorder.mutations) == 1
    assert recorder.mutations[0].field == "style.font_size"


def test_multiple_overrides_create_separate_records(monkeypatch) -> None:
    recorder = _activate_recorder(monkeypatch)
    node = _text_node()
    _apply_ir_overrides(
        node,
        WidgetIrOverrides(text="New", text_color="#FF0000", font_size=18.0),
    )
    fields = {mutation.field for mutation in recorder.mutations}
    assert fields == {"text", "style.text_color", "style.font_size"}
    assert len(recorder.mutations) == 3


def test_noop_override_creates_no_record(monkeypatch) -> None:
    recorder = _activate_recorder(monkeypatch)
    node = _text_node(text="Same")
    result = _apply_ir_overrides(node, WidgetIrOverrides(text="Same"))
    assert result.text == "Same"
    assert recorder.mutations == []


def test_absent_overrides_create_no_record(monkeypatch) -> None:
    recorder = _activate_recorder(monkeypatch)
    node = _text_node()
    assert _apply_ir_overrides(node, None) is node
    assert recorder.mutations == []


def test_recorder_disabled_merge_still_works() -> None:
    node = _text_node()
    result = _apply_ir_overrides(node, WidgetIrOverrides(text="Changed"))
    assert result.text == "Changed"


def test_clean_input_node_not_mutated_in_place() -> None:
    node = _text_node()
    result = _apply_ir_overrides(node, WidgetIrOverrides(text="Changed"))
    assert node.text == "Hello"
    assert result.text == "Changed"
    assert result is not node


def test_merge_ir_node_records_override_provenance(monkeypatch) -> None:
    recorder = _activate_recorder(monkeypatch)
    clean = _text_node()
    ir = WidgetIrNode(
        figma_id=clean.id,
        kind=WidgetIrKind.AUTO,
        overrides=WidgetIrOverrides(text="Merged"),
    )
    merged = merge_ir_node(clean, ir, omit_ids=frozenset())
    assert merged.text == "Merged"
    assert any(mutation.field == "text" for mutation in recorder.mutations)
