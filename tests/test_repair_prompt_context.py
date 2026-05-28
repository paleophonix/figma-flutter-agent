"""Tests for APR repair system prompt environment injection."""

from __future__ import annotations

from figma_flutter_agent.llm.prompts import (
    build_repair_system_prompt,
    render_repair_system_prompt,
)
from figma_flutter_agent.llm.repair_scope import (
    RepairEnvironmentContext,
    RepairScope,
    RepairTarget,
    build_repair_environment_context,
    dedupe_analyze_errors,
    format_line_numbered_source,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_format_line_numbered_source_uses_analyzer_aligned_prefix() -> None:
    numbered = format_line_numbered_source("void main() {\n  runApp();\n}")
    assert "1: void main()" in numbered
    assert "2:   runApp();" in numbered


def test_dedupe_analyze_errors_preserves_order() -> None:
    errors = [
        "error - a.dart:1:1 - x",
        "error - a.dart:1:1 - x",
        "error - b.dart:2:2 - y",
    ]
    assert dedupe_analyze_errors(errors) == [
        "error - a.dart:1:1 - x",
        "error - b.dart:2:2 - y",
    ]


def test_build_repair_environment_context_injects_l6_fields() -> None:
    tree = CleanDesignTreeNode(
        id="1:99",
        name="Button",
        type=NodeType.BUTTON,
        text="Sign in",
    )
    scope = RepairScope(
        targets=(
            RepairTarget(
                target="screenCode",
                widget_name=None,
                code="class SignInScreen {}",
                planned_path="lib/features/sign_in/sign_in_screen.dart",
                errors=("error - lib/features/sign_in/sign_in_screen.dart:2:5 - expected_token",),
                planned_excerpt="   2| class SignInScreen {}",
            ),
        ),
        unchanged_widget_names=("FooterWidget",),
    )
    planned = {
        "lib/features/sign_in/sign_in_screen.dart": (
            "import 'package:flutter/material.dart';\n"
            "class SignInScreen extends StatelessWidget {\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return const SizedBox(key: ValueKey('figma-1_99'));\n"
            "  }\n"
            "}\n"
        )
    }
    context = build_repair_environment_context(
        scope=scope,
        planned_files=planned,
        analyze_errors=list(scope.targets[0].errors),
        clean_tree=tree,
        failed_attempts_history=["Attempt 1 (failed):\n--- screenCode ---\nclass Bad {}"],
    )
    prompt = render_repair_system_prompt(context)
    assert "<L1:PURPOSE>" in prompt
    assert "<L6:ENVIRONMENT>" in prompt
    assert "expected_token" in prompt
    assert "строке 2" in context.analyze_errors
    assert "SignInScreen" in context.code
    assert "FooterWidget" in prompt
    assert "Attempt 1 (failed)" in prompt
    assert '"text": "Sign in"' in prompt or "Sign in" in prompt


def test_render_repair_system_prompt_safe_substitute_missing_history() -> None:
    context = RepairEnvironmentContext(
        analyze_errors="(none)",
        code="(empty file)",
        semantic_hint="null",
        failed_attempts_history="",
        unchanged_widget_names="(none)",
    )
    prompt = build_repair_system_prompt(context)
    assert "<L2:ROLE>" in prompt
    assert "null" in prompt
