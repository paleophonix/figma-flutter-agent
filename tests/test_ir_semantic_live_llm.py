"""Optional live LLM semantic IR smoke (skipped by default)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.llm.clients import create_llm_client
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "semantic_ir" / "feedback_layout.json"

pytestmark = pytest.mark.live_llm


@pytest.fixture
def feedback_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="live LLM API key not configured",
)
@pytest.mark.asyncio
async def test_live_generate_returns_semantic_verdicts_for_feedback(
    feedback_tree: CleanDesignTreeNode,
    tmp_path: Path,
) -> None:
    settings = Settings()
    if not settings.llm_api_key():
        pytest.skip("LLM API key missing")
    client = create_llm_client(
        provider=settings.resolved_llm_provider(),
        api_key=settings.llm_api_key() or "",
        model=settings.resolved_llm_generate_model(),
        require_strict_json_schema=settings.llm_require_strict_json_schema,
    )
    response = await client.generate_async(
        feedback_tree,
        DesignTokens(),
        feature_name="feedback",
        asset_manifest=[],
        use_screen_ir=True,
        require_screen_ir=True,
        project_dir=tmp_path,
    )
    assert response.screen_ir is not None
    roles = {verdict.role for verdict in response.screen_ir.semantic_verdicts}
    node_ids = {verdict.node_id for verdict in response.screen_ir.semantic_verdicts}
    assert response.screen_ir.semantic_summary is not None or response.screen_ir.semantic_verdicts
    assert "281:7386" in node_ids or any("rating" in role for role in roles)
    assert any("textarea" in role or "text_input" in role for role in roles) or any(
        verdict.subtype and "textarea" in verdict.subtype
        for verdict in response.screen_ir.semantic_verdicts
    )
    assert any("submit" in role or "button" in role for role in roles)
