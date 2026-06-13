"""ScreenIr semantic verdict schema compatibility tests."""

from __future__ import annotations

import json

from figma_flutter_agent.llm.schema import generation_json_schema
from figma_flutter_agent.schemas import FlutterGenerationResponse, ScreenIr, WidgetIrNode
from figma_flutter_agent.schemas.ir import (
    SemanticControlVerdict,
    SemanticContractTraits,
    SemanticScreenSummary,
)


def test_legacy_screen_ir_without_semantic_fields_parses() -> None:
    payload = {
        "screenIr": {
            "root": {"figmaId": "1:1", "children": []},
            "omitFigmaIds": [],
            "stateByFigmaId": {},
            "adaptiveRules": [],
        },
        "extractedWidgets": [],
    }
    response = FlutterGenerationResponse.model_validate(payload)
    assert response.screen_ir is not None
    assert response.screen_ir.semantic_summary is None
    assert response.screen_ir.semantic_verdicts == []


def test_screen_ir_with_semantic_fields_serializes_round_trip() -> None:
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="281:7179"),
        semantic_summary=SemanticScreenSummary(
            screen_role="feedback_form",
            confidence=0.9,
            explanation="Survey screen",
            warnings=[],
        ),
        semantic_verdicts=[
            SemanticControlVerdict(
                node_id="281:7386",
                role="rating_input",
                subtype="star_rating",
                control_node_id="281:7386",
                boundary_node_id="281:7386",
                label_node_ids=["281:7261"],
                contract_kind="rating_input",
                contract_traits=SemanticContractTraits(rating_value=4, rating_max=5),
                proposed_layout_laws=["rating_value_from_component_variant"],
                value=4,
                confidence=0.95,
                proposed_effects=["emit_rating_control"],
                explanation="Variant Rating=4",
            ),
        ],
    )
    dumped = screen_ir.model_dump(by_alias=True, mode="json")
    restored = ScreenIr.model_validate(dumped)
    assert restored.semantic_summary is not None
    assert restored.semantic_summary.screen_role == "feedback_form"
    assert restored.semantic_verdicts[0].contract_kind == "rating_input"
    assert restored.semantic_verdicts[0].proposed_layout_laws == ["rating_value_from_component_variant"]


def _resolve_screen_ir_schema(schema: dict[str, object]) -> dict[str, object]:
    screen_ir_ref = schema["properties"]["screenIr"]
    if isinstance(screen_ir_ref, dict) and "anyOf" in screen_ir_ref:
        for option in screen_ir_ref["anyOf"]:
            if isinstance(option, dict) and "$ref" in option:
                ref = str(option["$ref"]).rsplit("/", maxsplit=1)[-1]
                defs = schema.get("$defs") or schema.get("definitions") or {}
                return defs[ref]
    if isinstance(screen_ir_ref, dict) and "$ref" in screen_ir_ref:
        ref = str(screen_ir_ref["$ref"]).rsplit("/", maxsplit=1)[-1]
        defs = schema.get("$defs") or schema.get("definitions") or {}
        return defs[ref]
    return screen_ir_ref  # type: ignore[return-value]


def test_generation_json_schema_includes_semantic_fields() -> None:
    schema = generation_json_schema(strict=True)
    screen_ir_schema = _resolve_screen_ir_schema(schema)
    assert "semanticSummary" in screen_ir_schema["properties"]
    assert "semanticVerdicts" in screen_ir_schema["properties"]


def test_flutter_generation_response_json_round_trip() -> None:
    payload = {
        "screenIr": {
            "root": {"figmaId": "281:7179"},
            "semanticSummary": {"screenRole": "feedback", "confidence": 0.8},
            "semanticVerdicts": [
                {
                    "nodeId": "281:7600",
                    "role": "button",
                    "subtype": "submit",
                    "labelNodeIds": [],
                    "confidence": 0.9,
                    "proposedEffects": ["wire_primary_action"],
                }
            ],
        },
        "extractedWidgets": [],
    }
    text = json.dumps(payload)
    restored = FlutterGenerationResponse.model_validate(json.loads(text))
    assert restored.screen_ir is not None
    assert restored.screen_ir.semantic_verdicts[0].role == "button"
