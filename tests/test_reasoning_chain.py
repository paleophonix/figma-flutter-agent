"""Tests for reasoning chain."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain


def test_reasoning_chain_cumulative() -> None:
    chain = ReasoningChain()
    chain.append("recognise", {"step": "recognise", "symptoms": []})
    chain.append("inspect", {"step": "inspect", "entities": []})
    prior = chain.prior_steps("diagnose")
    assert set(prior) == {"recognise", "inspect"}
    assert "diagnose" not in prior
