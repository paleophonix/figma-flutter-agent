"""Tests for schema gate validation."""

from __future__ import annotations

import pytest

from figma_flutter_agent.dev.opencode.schema_gate import coerce_step_output, validate_step_output
from figma_flutter_agent.errors import FigmaFlutterError


def test_validate_diagnose_requires_laws() -> None:
    with pytest.raises(FigmaFlutterError, match="laws"):
        validate_step_output("diagnose", {"step": "diagnose"})


def test_validate_diagnose_ok() -> None:
    result = validate_step_output("diagnose", {"step": "diagnose", "laws": []})
    assert result["step"] == "diagnose"


def test_coerce_step_output_injects_missing_step() -> None:
    result = coerce_step_output("diagnose", {"laws": [], "blocked": False})
    assert result["step"] == "diagnose"
    assert result["laws"] == []


def test_coerce_step_output_rejects_mismatch() -> None:
    with pytest.raises(FigmaFlutterError, match="inspect"):
        coerce_step_output("diagnose", {"step": "inspect", "laws": []})
