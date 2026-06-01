"""Analyzer diagnostic summarization for repair logging."""

from __future__ import annotations

from figma_flutter_agent.generator.validation import (
    PlannedAnalyzeOutcome,
    summarize_analyze_diagnostics,
)


def test_summarize_analyze_diagnostics_splits_errors_and_warnings() -> None:
    output = "\n".join(
        [
            "Analyzing demo_app...",
            "  error - lib/foo.dart:10:3 - Undefined name 'x'.",
            "  warning - lib/foo.dart:12:5 - Unused import.",
        ]
    )
    errors, warnings = summarize_analyze_diagnostics(output, detail="flutter analyze failed")
    assert len(errors) == 1
    assert "Undefined name" in errors[0]
    assert len(warnings) == 1
    assert "Unused import" in warnings[0]


def test_summarize_analyze_diagnostics_passed_false_outcome() -> None:
    """PlannedAnalyzeOutcome with passed=False: errors/warnings counts are correct."""
    analyze_output = "\n".join(
        [
            "Analyzing demo_app...",
            "  error - lib/x.dart:1:1 - foo",
            "  warning - lib/x.dart:2:1 - bar",
            "  warning - lib/x.dart:3:1 - baz",
        ]
    )
    outcome = PlannedAnalyzeOutcome(
        skipped=False,
        passed=False,
        detail="flutter analyze failed",
        errors=("error - lib/x.dart:1:1 - foo",),
        analyze_output=analyze_output,
    )
    errors, warnings = summarize_analyze_diagnostics(outcome.analyze_output, detail=outcome.detail)
    assert len(errors) == 1, f"expected 1 error, got {len(errors)}"
    assert len(warnings) == 2, f"expected 2 warnings, got {len(warnings)}"
    assert not outcome.passed


def test_summarize_analyze_diagnostics_no_diagnostics_returns_empty() -> None:
    """When output has no error/warning lines, both tuples are empty."""
    output = "Analyzing demo_app...\nNo issues found!"
    errors, warnings = summarize_analyze_diagnostics(output, detail="ok")
    assert errors == ()
    assert warnings == ()
