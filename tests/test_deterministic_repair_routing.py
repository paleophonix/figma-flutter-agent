"""Deterministic analyzer-error routing must bypass LLM repair."""

from __future__ import annotations

from figma_flutter_agent.stages.llm_repair.deterministic import (
    errors_are_deterministic_analyzer_failures,
    errors_block_llm_repair,
)


def test_undefined_named_parameter_blocks_llm_repair() -> None:
    errors = (
        "lib/generated/sign_up_layout.dart:42:9 - "
        "The named parameter 'label' isn't defined - undefined_named_parameter",
    )
    assert errors_are_deterministic_analyzer_failures(errors, "dart analyze")
    assert errors_block_llm_repair(errors, "dart analyze")


def test_missing_import_is_deterministic() -> None:
    errors = (
        "lib/widgets/header_widget.dart:2:8 - "
        "Target of URI doesn't exist - uri_does_not_exist",
    )
    assert errors_are_deterministic_analyzer_failures(errors, "dart analyze")
