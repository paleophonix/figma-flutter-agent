"""Tests for diagnose output validation."""

from __future__ import annotations

import pytest

from figma_flutter_agent.dev.opencode.diagnose_validate import (
    diagnose_laws_missing,
    inspect_anchors_compiler_surfaces,
    validate_diagnose_output,
)
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.errors import FigmaFlutterError


def _chain_with_compiler_inspect() -> ReasoningChain:
    chain = ReasoningChain()
    chain.append(
        "inspect",
        {
            "entities": [
                {
                    "id": "e1",
                    "repoPaths": [
                        "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                    ],
                }
            ]
        },
    )
    return chain


def test_validate_diagnose_rejects_empty_laws_when_inspect_anchors_compiler() -> None:
    chain = _chain_with_compiler_inspect()
    with pytest.raises(FigmaFlutterError, match="laws\\[\\] is empty"):
        validate_diagnose_output({"laws": [], "blocked": False}, chain)


def test_validate_diagnose_accepts_laws_when_inspect_anchors_compiler() -> None:
    chain = _chain_with_compiler_inspect()
    validate_diagnose_output(
        {"laws": [{"id": "law-flex-overflow"}], "blocked": False},
        chain,
    )


def test_diagnose_laws_missing_ignores_capture_only_inspect() -> None:
    chain = ReasoningChain()
    chain.append(
        "inspect",
        {
            "entities": [
                {
                    "id": "e1",
                    "repoPaths": ["debug/capture.py"],
                }
            ]
        },
    )
    assert not diagnose_laws_missing({"laws": [], "blocked": False}, chain)
    assert not inspect_anchors_compiler_surfaces(chain)
