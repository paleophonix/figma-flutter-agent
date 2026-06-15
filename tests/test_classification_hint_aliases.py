"""Classification hint contract-kind alias normalization."""

from __future__ import annotations

import pytest

from figma_flutter_agent.schemas import FlutterGenerationResponse, WidgetIrKind
from figma_flutter_agent.schemas.ir import ScreenIr, WidgetIrNode
from figma_flutter_agent.schemas.ir_payloads import (
    LlmClassificationHint,
    normalize_classification_hint_kind,
)


def test_normalize_maps_choice_chip_group_to_chip_choice() -> None:
    assert normalize_classification_hint_kind("choice_chip_group") == "chip_choice"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("rating_input", "input_rating"),
        ("star_rating", "input_rating"),
        ("input_rating", "input_rating"),
    ],
)
def test_normalize_maps_rating_contract_kinds(raw: str, expected: str) -> None:
    assert normalize_classification_hint_kind(raw) == expected


def test_classification_hint_accepts_contract_kind_aliases() -> None:
    hint = LlmClassificationHint(suggested_kind="choice_chip_group", confidence=0.7)
    assert hint.suggested_kind == "chip_choice"

    rating_hint = LlmClassificationHint(suggested_kind="input_rating", confidence=0.65)
    assert rating_hint.suggested_kind == "input_rating"


def test_classification_hint_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="not a valid WidgetIrKind"):
        LlmClassificationHint(suggested_kind="totally_made_up_kind", confidence=0.6)


def test_flutter_generation_response_accepts_feedback_style_hints() -> None:
    def _hint_node(figma_id: str, suggested: str) -> WidgetIrNode:
        return WidgetIrNode(
            figma_id=figma_id,
            kind=WidgetIrKind.AUTO,
            children=[],
            classification_hint=LlmClassificationHint(
                suggested_kind=suggested,
                confidence=0.7,
            ),
        )

    response = FlutterGenerationResponse(
        screen_ir=ScreenIr(
            root=WidgetIrNode(
                figma_id="281:7179",
                kind=WidgetIrKind.STACK,
                children=[
                    WidgetIrNode(figma_id="281:7189", kind=WidgetIrKind.AUTO, children=[]),
                    WidgetIrNode(
                        figma_id="281:7446",
                        kind=WidgetIrKind.COLUMN,
                        children=[
                            WidgetIrNode(
                                figma_id="281:7432",
                                kind=WidgetIrKind.COLUMN,
                                children=[
                                    WidgetIrNode(
                                        figma_id="281:7431",
                                        kind=WidgetIrKind.COLUMN,
                                        children=[
                                            WidgetIrNode(
                                                figma_id="281:7244",
                                                kind=WidgetIrKind.TEXT,
                                                children=[],
                                            ),
                                            _hint_node("281:7386", "input_rating"),
                                        ],
                                    ),
                                ],
                            ),
                            WidgetIrNode(
                                figma_id="281:7430",
                                kind=WidgetIrKind.COLUMN,
                                children=[
                                    WidgetIrNode(
                                        figma_id="281:7279",
                                        kind=WidgetIrKind.TEXT,
                                        children=[],
                                    ),
                                    _hint_node("281:7427", "choice_chip_group"),
                                ],
                            ),
                            WidgetIrNode(
                                figma_id="281:7429",
                                kind=WidgetIrKind.COLUMN,
                                children=[
                                    WidgetIrNode(
                                        figma_id="281:7280",
                                        kind=WidgetIrKind.TEXT,
                                        children=[],
                                    ),
                                    _hint_node("281:7428", "choice_chip_group"),
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ),
        extracted_widgets=[],
    )
    assert (
        response.screen_ir.root.children[1].children[0].children[0].children[1].classification_hint
        is not None
    )
    assert (
        response.screen_ir.root.children[1]
        .children[0]
        .children[0]
        .children[1]
        .classification_hint.suggested_kind
        == "input_rating"
    )
