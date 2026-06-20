"""Tests for schema gate validation."""

from __future__ import annotations

import pytest

from figma_flutter_agent.dev.opencode.schema_gate import validate_step_output
from figma_flutter_agent.errors import FigmaFlutterError


def test_validate_diagnose_requires_laws() -> None:
    with pytest.raises(FigmaFlutterError, match="laws"):
        validate_step_output("diagnose", {"step": "diagnose"})


def test_validate_diagnose_ok() -> None:
    validate_step_output("diagnose", {"step": "diagnose", "laws": []})
