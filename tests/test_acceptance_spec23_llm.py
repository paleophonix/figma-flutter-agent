"""Section-23 acceptance for the LLM codegen path (fixture-backed)."""

import json
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.schemas import FlutterGenerationResponse
from figma_flutter_agent.validation.spec23 import Spec23Report, evaluate_spec23_llm_path


def test_spec23_llm_path_passes_with_fixture_response() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    generation = FlutterGenerationResponse.model_validate(
        json.loads(Path("tests/fixtures/llm_response_sample.json").read_text(encoding="utf-8"))
    )

    report = evaluate_spec23_llm_path(
        root, Settings(), generation=generation, node_id=root["id"], strict=True
    )

    assert report.generation_mode == "llm"
    assert report.passed, _format_failed(report)


def test_spec23_llm_path_plans_screen_without_layout_delegate() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    generation = FlutterGenerationResponse.model_validate(
        json.loads(Path("tests/fixtures/llm_response_sample.json").read_text(encoding="utf-8"))
    )

    report = evaluate_spec23_llm_path(
        root, Settings(), generation=generation, node_id=root["id"], strict=True
    )
    production = next(item for item in report.criteria if item.name == "production_ready_code")

    assert production.passed
    assert production.detail == "llm"


def _format_failed(report: Spec23Report) -> str:
    return "; ".join(f"{item.name}: {item.detail}" for item in report.criteria if not item.passed)
