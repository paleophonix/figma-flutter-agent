"""Contract-oriented semantic verdict schema tests."""

from __future__ import annotations

from figma_flutter_agent.llm.schema import generation_json_schema
from figma_flutter_agent.schemas import ScreenIr, WidgetIrNode
from figma_flutter_agent.schemas.ir import (
    SemanticContractTraits,
    SemanticControlVerdict,
    SemanticOptionVerdict,
)
from tests.test_ir_semantic_schema import _resolve_screen_ir_schema


def test_contract_fields_round_trip_on_semantic_control_verdict() -> None:
    verdict = SemanticControlVerdict(
        node_id="281:7500",
        role="text_input",
        subtype="textarea",
        control_node_id="281:7500",
        boundary_node_id="281:7500",
        label_node_ids=["281:7499"],
        placeholder_node_ids=["281:7500"],
        value_node_ids=[],
        contract_kind="textarea",
        contract_traits=SemanticContractTraits(
            is_multiline=True,
            keyboard_intent="text",
        ),
        proposed_layout_laws=[
            "multiline_input_top_align",
            "label_outside_control",
            "placeholder_as_hint",
        ],
        proposed_effects=[
            "attach_hint",
            "emit_multiline_text_field",
            "collapse_visual_group_to_input_contract",
        ],
        confidence=0.92,
        explanation="Text Area component with external label and placeholder copy",
    )
    restored = SemanticControlVerdict.model_validate(
        verdict.model_dump(by_alias=True, mode="json"),
    )
    assert restored.contract_traits is not None
    assert restored.contract_traits.is_multiline is True
    assert restored.label_node_ids == ["281:7499"]


def test_feedback_reference_contract_verdicts_validate() -> None:
    """Static reference payloads for feedback fixture — schema capacity only."""
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="281:7179"),
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
                proposed_effects=["emit_rating_control"],
                value=4,
                confidence=0.95,
            ),
            SemanticControlVerdict(
                node_id="281:7401",
                role="choice_input",
                subtype="chip_group",
                control_node_id="281:7401",
                boundary_node_id="281:7401",
                label_node_ids=["281:7400"],
                option_node_ids=["281:7402", "281:7403"],
                contract_kind="choice_chip_group",
                options=[
                    SemanticOptionVerdict(node_id="281:7402", label="Design"),
                    SemanticOptionVerdict(node_id="281:7403", label="Prototype"),
                ],
                proposed_layout_laws=["selected_chip_state_preserved"],
                proposed_effects=["emit_choice_chip_group"],
                confidence=0.88,
            ),
            SemanticControlVerdict(
                node_id="281:7500",
                role="text_input",
                subtype="textarea",
                control_node_id="281:7500",
                boundary_node_id="281:7500",
                label_node_ids=["281:7499"],
                placeholder_node_ids=["281:7500"],
                contract_kind="textarea",
                contract_traits=SemanticContractTraits(is_multiline=True),
                proposed_layout_laws=["multiline_input_top_align", "placeholder_as_hint"],
                proposed_effects=["attach_hint", "emit_multiline_text_field"],
                confidence=0.9,
            ),
            SemanticControlVerdict(
                node_id="281:7600",
                role="button",
                subtype="submit",
                control_node_id="281:7600",
                boundary_node_id="281:7600",
                contract_kind="button",
                contract_traits=SemanticContractTraits(action_kind="submit"),
                proposed_layout_laws=["primary_button_action_role"],
                proposed_effects=["emit_native_text_field"],
                confidence=0.93,
            ),
        ],
    )
    restored = ScreenIr.model_validate(screen_ir.model_dump(by_alias=True, mode="json"))
    by_id = {verdict.node_id: verdict for verdict in restored.semantic_verdicts}
    assert by_id["281:7386"].contract_traits is not None
    assert by_id["281:7386"].contract_traits.rating_value == 4
    assert by_id["281:7500"].contract_kind == "textarea"
    assert "281:7499" in by_id["281:7500"].label_node_ids
    assert "multiline_input_top_align" in by_id["281:7500"].proposed_layout_laws
    assert by_id["281:7401"].contract_kind == "choice_chip_group"


def test_generation_json_schema_exposes_contract_fields() -> None:
    schema = generation_json_schema(strict=True)
    screen_ir_schema = _resolve_screen_ir_schema(schema)
    verdict_schema = screen_ir_schema["properties"]["semanticVerdicts"]["items"]
    if "$ref" in verdict_schema:
        ref = str(verdict_schema["$ref"]).rsplit("/", maxsplit=1)[-1]
        defs = schema.get("$defs") or schema.get("definitions") or {}
        verdict_schema = defs[ref]
    props = verdict_schema["properties"]
    assert "contractKind" in props
    assert "contractTraits" in props
    assert "proposedLayoutLaws" in props
    assert "controlNodeId" in props
    assert "placeholderNodeIds" in props
