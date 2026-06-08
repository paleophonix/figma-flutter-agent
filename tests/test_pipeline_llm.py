"""Tests for LLM pipeline orchestration helpers."""

import pytest

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.pipeline.llm import (
    ensure_llm_output_or_raise,
    warn_if_llm_screen_delegates_to_layout,
)
from figma_flutter_agent.stages import LlmStageResult


def test_ensure_llm_output_or_raise_honors_force_llm_regen() -> None:
    with pytest.raises(LlmError, match="no LLM output"):
        ensure_llm_output_or_raise(
            llm_result=LlmStageResult(llm_attempted=True),
            tree_changed=False,
            force_llm_regen=True,
        )


def test_warn_if_llm_screen_delegates_to_layout() -> None:
    warnings: list[str] = []
    warn_if_llm_screen_delegates_to_layout(
        warnings,
        planned_files={
            "lib/features/reminders/reminders_screen.dart": (
                "import 'package:demo_app/generated/reminders_layout.dart';\n"
                "class RemindersScreen extends StatelessWidget {\n"
                "  Widget build(BuildContext context) => const RemindersLayout();\n"
                "}\n"
            )
        },
        feature_name="reminders",
    )
    assert warnings
    assert "RemindersLayout" in warnings[0]
