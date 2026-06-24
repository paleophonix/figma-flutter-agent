"""Fake IR LLM flow tests for report-only semantic verdicts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.debug.ir_dumps import write_ir_debug_json
from figma_flutter_agent.generator.ir.context import IrEmitContext, IrEmitPolicy
from figma_flutter_agent.generator.ir.materialize import materialize_screen_code_from_ir
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.llm.clients.openai import OpenAiLlmClient
from figma_flutter_agent.llm.payload_format import parse_labeled_user_payload
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
)
from figma_flutter_agent.schemas.ir import (
    SemanticContractTraits,
    SemanticControlVerdict,
    SemanticScreenSummary,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "semantic_ir" / "feedback_layout.json"


def _feedback_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def _semantic_generation(tree: CleanDesignTreeNode) -> FlutterGenerationResponse:
    screen_ir = default_screen_ir(tree)
    screen_ir = screen_ir.model_copy(
        update={
            "semantic_summary": SemanticScreenSummary(
                screen_role="feedback_form",
                confidence=0.88,
                explanation="Feedback survey",
                warnings=[],
            ),
            "semantic_verdicts": [
                SemanticControlVerdict(
                    node_id="281:7386",
                    role="rating_input",
                    subtype="star_rating",
                    contract_kind="rating_input",
                    contract_traits=SemanticContractTraits(rating_value=4),
                    proposed_layout_laws=["rating_value_from_component_variant"],
                    confidence=0.9,
                    proposed_effects=["emit_rating_control"],
                ),
            ],
        },
    )
    return FlutterGenerationResponse(screen_ir=screen_ir, extracted_widgets=[])


class _FakeSemanticClient(OpenAiLlmClient):
    """Minimal client stub exposing prompt build + finalize without network."""

    def __init__(self) -> None:
        super().__init__(api_key="test", model="gpt-test")

    def _request_generation(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError


def test_build_user_prompt_includes_semantic_context_sections() -> None:
    tree = _feedback_tree()
    client = _FakeSemanticClient()
    prompt = client._build_user_prompt(
        tree,
        DesignTokens(),
        feature_name="feedback",
        asset_manifest=[],
        use_screen_ir=True,
    )
    sections = parse_labeled_user_payload(prompt)
    assert "cleanTree" in sections
    assert "treeOutline" in sections
    assert "textInventory" in sections
    assert "componentInventory" in sections
    assert "relationshipHints" in sections
    assert "rawContext" not in sections
    assert "geometryInventory" not in sections
    assert sections["cleanTree"]["name"] == "Feedback"


def test_finalize_generation_preserves_semantic_verdicts(tmp_path: Path) -> None:
    tree = _feedback_tree()
    client = _FakeSemanticClient()
    generation = _semantic_generation(tree)
    finalized = client._finalize_generation_response(
        generation,
        clean_tree=tree,
        use_screen_ir=True,
        require_screen_ir=True,
        project_dir=tmp_path,
        tokens=DesignTokens(),
        feature_name="feedback",
    )
    assert finalized.screen_ir is not None
    assert finalized.screen_ir.semantic_summary is not None
    assert finalized.screen_ir.semantic_verdicts[0].node_id == "281:7386"
    dump_path = tmp_path / ".debug" / "ir" / "feedback_llm_parsed.json"
    assert dump_path.is_file()
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    assert payload["screenIr"]["semanticVerdicts"]


def test_materialize_emit_ignores_semantic_verdicts() -> None:
    tree = _feedback_tree()
    ctx = IrEmitContext(policy=IrEmitPolicy(validate=False, apply_guards=False))
    baseline = FlutterGenerationResponse(screen_ir=default_screen_ir(tree), extracted_widgets=[])
    with_semantics = _semantic_generation(tree)
    baseline_out = materialize_screen_code_from_ir(
        baseline,
        clean_tree=tree,
        feature_name="feedback",
        ctx=ctx,
        materialize_screen_body=True,
        materialize_extracted=False,
    )
    semantic_out = materialize_screen_code_from_ir(
        with_semantics,
        clean_tree=tree,
        feature_name="feedback",
        ctx=ctx,
        materialize_screen_body=True,
        materialize_extracted=False,
    )
    assert baseline_out.screen_code == semantic_out.screen_code


def test_write_ir_debug_json_semantic_context_stage(tmp_path: Path) -> None:
    path = write_ir_debug_json(
        stage="semantic_context",
        feature_name="feedback",
        payload={"rawContext": {"id": "281:7179"}},
        project_dir=tmp_path,
    )
    assert path.name == "feedback_semantic_context.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["stage"] == "semantic_context"
    assert payload["rawContext"]["id"] == "281:7179"
