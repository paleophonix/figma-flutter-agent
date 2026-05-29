"""Tests for screen IR LLM prompts and response validation."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.generator.ir_tree import default_screen_ir
from figma_flutter_agent.llm.client import BaseLlmClient
from figma_flutter_agent.llm.ir_payload import dump_screen_ir_blueprint
from figma_flutter_agent.llm.prompts import build_system_prompt
from figma_flutter_agent.llm.schema import generation_json_schema
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FlutterGenerationResponse,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


def test_generation_json_schema_includes_screen_ir() -> None:
    schema = generation_json_schema(strict=True)
    props = schema["properties"]
    assert "screenIr" in props
    assert "screenCode" in props


def test_build_system_prompt_screen_ir_mode() -> None:
    prompt = build_system_prompt(use_screen_ir=True)
    assert "screenIr" in prompt
    assert "Do NOT emit `screenCode`" in prompt


def test_dump_screen_ir_blueprint_matches_tree_ids() -> None:
    root = CleanDesignTreeNode(
        id="1",
        name="Col",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="2", name="T", type=NodeType.TEXT, text="Hi"),
        ],
    )
    blueprint = dump_screen_ir_blueprint(root)
    assert blueprint["root"]["figmaId"] == "1"
    assert blueprint["root"]["children"][0]["figmaId"] == "2"


def test_flutter_generation_response_requires_payload() -> None:
    with pytest.raises(ValueError, match="screenIr or screenCode"):
        FlutterGenerationResponse()


def test_flutter_generation_response_accepts_screen_ir_only() -> None:
    ir = default_screen_ir(
        CleanDesignTreeNode(id="1", name="R", type=NodeType.ROW, children=[]),
    )
    response = FlutterGenerationResponse(screen_ir=ir)
    assert response.screen_ir is not None
    assert response.resolved_screen_code() == ""


class _StubLlmClient(BaseLlmClient):
    def _request_generation(self, prompt, *, system_prompt, **kwargs):  # type: ignore[no-untyped-def]
        del prompt, system_prompt, kwargs
        raise NotImplementedError

    def repair(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def repair_async(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def refine(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def refine_async(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError


def test_finalize_generation_response_validates_screen_ir() -> None:
    client = _StubLlmClient(
        "test",
        provider="openai",
        strict_json_schema=True,
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Col",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="2", name="T", type=NodeType.TEXT, text="x"),
        ],
    )
    ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1",
            kind=WidgetIrKind.AUTO,
            children=[WidgetIrNode(figma_id="2", kind=WidgetIrKind.AUTO)],
        ),
    )
    response = FlutterGenerationResponse(screen_ir=ir)
    finalized = client._finalize_generation_response(
        response,
        clean_tree=root,
        use_screen_ir=True,
    )
    assert finalized.screen_ir is not None


def test_finalize_generation_response_requires_ir_when_enabled() -> None:
    client = _StubLlmClient(
        "test",
        provider="openai",
        strict_json_schema=True,
    )
    root = CleanDesignTreeNode(id="1", name="Col", type=NodeType.COLUMN, children=[])
    empty = FlutterGenerationResponse.model_construct(screen_ir=None, screen_code=None)
    with pytest.raises(LlmError, match="missing screenIr"):
        client._finalize_generation_response(
            empty,
            clean_tree=root,
            use_screen_ir=True,
        )
