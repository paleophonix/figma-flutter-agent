"""Semantics fixture corpus runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.parser.semantics.corpus import (
    CorpusCase,
    load_fixture_payload,
    parse_corpus_case,
    run_case,
)
from figma_flutter_agent.schemas import WidgetIrKind
from tests.support.semantics_trees import (
    compact_stack_tooltip_trap,
    compact_vector_loader_trap,
    feedback_loader_variant,
    feedback_tooltip_variant,
    filled_button,
    initial_letter_square_trap,
    size_picker_row,
    weekday_chip_row,
)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "layouts" / "semantics"


def _load_case(path: Path) -> CorpusCase:
    return parse_corpus_case(path, load_fixture_payload(path))


def _fixture_paths() -> list[Path]:
    if not FIXTURE_ROOT.exists():
        return []
    return sorted(FIXTURE_ROOT.glob("**/*.json"))


@pytest.mark.parametrize("fixture_path", _fixture_paths(), ids=lambda p: p.relative_to(FIXTURE_ROOT).as_posix())
def test_semantics_fixture_corpus(fixture_path: Path) -> None:
    result = run_case(_load_case(fixture_path))
    assert result.passed, result.message


def test_programmatic_chip_choice_positive() -> None:
    tree = weekday_chip_row()
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    screen_ir = default_screen_ir(tree)
    updated, _ = classify_screen_ir(screen_ir, tree)
    kind = _find_kind(updated.root, "chip-row")
    assert kind == WidgetIrKind.CHIP_CHOICE.value


def test_programmatic_size_picker_negative() -> None:
    tree = size_picker_row()
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    screen_ir = default_screen_ir(tree)
    updated, _ = classify_screen_ir(screen_ir, tree)
    kind = _find_kind(updated.root, "size-picker")
    assert kind not in {WidgetIrKind.CHIP_CHOICE.value, WidgetIrKind.CHIP_FILTER.value}


def test_programmatic_button_filled() -> None:
    tree = filled_button()
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    updated, _ = classify_screen_ir(default_screen_ir(tree), tree)
    assert _find_kind(updated.root, "btn-filled") == WidgetIrKind.BUTTON_FILLED.value


def test_w1_corpus_gate_integration() -> None:
    from figma_flutter_agent.parser.semantics.metrics import evaluate_w1_corpus

    report = evaluate_w1_corpus()
    assert report.passed


def test_programmatic_avatar_trap() -> None:
    tree = initial_letter_square_trap()
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    updated, _ = classify_screen_ir(default_screen_ir(tree), tree)
    assert _find_kind(updated.root, "initial-trap") != WidgetIrKind.MEDIA_AVATAR.value


def test_small_vector_not_feedback_loader() -> None:
    tree = compact_vector_loader_trap()
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    updated, _ = classify_screen_ir(default_screen_ir(tree), tree)
    kind = _find_kind(updated.root, "compact-vector-trap")
    assert kind != WidgetIrKind.FEEDBACK_LOADER.value


def test_small_stack_not_feedback_tooltip() -> None:
    tree = compact_stack_tooltip_trap()
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    updated, _ = classify_screen_ir(default_screen_ir(tree), tree)
    kind = _find_kind(updated.root, "compact-stack-trap")
    assert kind != WidgetIrKind.FEEDBACK_TOOLTIP.value


def test_vector_loader_variant_still_classifies() -> None:
    tree = feedback_loader_variant()
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    updated, _ = classify_screen_ir(default_screen_ir(tree), tree)
    assert _find_kind(updated.root, "loader-1") == WidgetIrKind.FEEDBACK_LOADER.value


def test_stack_tooltip_variant_still_classifies() -> None:
    tree = feedback_tooltip_variant()
    from figma_flutter_agent.generator.ir.tree import default_screen_ir
    from figma_flutter_agent.parser.semantics.classify import classify_screen_ir

    updated, _ = classify_screen_ir(default_screen_ir(tree), tree)
    assert _find_kind(updated.root, "tooltip-1") == WidgetIrKind.FEEDBACK_TOOLTIP.value


def _find_kind(node, figma_id: str) -> str | None:
    if node.figma_id == figma_id:
        return node.kind.value
    for child in node.children:
        found = _find_kind(child, figma_id)
        if found is not None:
            return found
    return None
