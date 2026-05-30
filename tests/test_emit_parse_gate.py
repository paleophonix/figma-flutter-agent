"""Emit parse gate (dart format on planned files in temp tree)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.config import AgentYamlConfig
from figma_flutter_agent.generator.validation import gate_planned_dart_syntax
from figma_flutter_agent.dev.flutter_sdk import resolve_dart_executable


def test_require_screen_ir_enables_emit_parse_gate() -> None:
    agent = AgentYamlConfig.model_validate(
        {
            "generation": {
                "use_deterministic_screen": False,
                "use_screen_ir": True,
                "require_screen_ir": True,
                "llm_fallback_to_deterministic": True,
            },
            "validation": {"emit_parse_gate": False},
        }
    )
    assert agent.generation.require_screen_ir is True
    assert agent.generation.use_screen_ir is True
    assert agent.generation.use_deterministic_screen is False
    assert agent.validation.emit_parse_gate is True
    assert agent.generation.llm_fallback_to_deterministic is False


def test_gate_rejects_unparseable_planned_dart() -> None:
    if resolve_dart_executable() is None:
        pytest.skip("dart SDK not available")
    planned = {
        "lib/features/foo/foo_screen.dart": (
            "import 'package:flutter/material.dart';\n\n"
            "class FooScreen extends StatelessWidget {\n"
            "  @override\n"
            "  Widget build(BuildContext context) => Stack(children: [Text('x'\n"
            ");\n"
            "}\n"
        ),
    }
    outcome = gate_planned_dart_syntax(
        planned,
        package_name="demo_app",
        require_dart_sdk=True,
    )
    assert not outcome.skipped
    assert not outcome.passed
    assert "parse" in outcome.detail.lower() or outcome.errors


def test_gate_accepts_minimal_valid_screen() -> None:
    if resolve_dart_executable() is None:
        pytest.skip("dart SDK not available")
    planned = {
        "lib/features/foo/foo_screen.dart": (
            "import 'package:flutter/material.dart';\n\n"
            "class FooScreen extends StatelessWidget {\n"
            "  const FooScreen({super.key});\n\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return const Scaffold(body: Center(child: Text('ok')));\n"
            "  }\n"
            "}\n"
        ),
    }
    outcome = gate_planned_dart_syntax(
        planned,
        package_name="demo_app",
        require_dart_sdk=True,
    )
    assert outcome.passed
