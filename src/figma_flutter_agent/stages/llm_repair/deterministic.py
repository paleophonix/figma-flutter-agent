"""Deterministic analyzer-error classification and repair routing."""

from __future__ import annotations

from typing import Any

_DETERMINISTIC_MARKERS = (
    "undefined_named_parameter",
    "undefined_method",
    "creation_with_non_type",
    "uri_does_not_exist",
    "isn't a class",
    "undefined_class",
    "missing_required_param",
    "argument_type_not_assignable",
)

_NON_LLM_REPAIRABLE = (
    "undefined_named_parameter",
    "isn't a class",
    "creation_with_non_type",
)


def errors_are_deterministic_analyzer_failures(errors: tuple[str, ...], detail: str) -> bool:
    """Return True when analyzer failures are structural, not LLM-repairable."""
    joined = f"{detail} {' '.join(errors)}".lower()
    return any(marker in joined for marker in _DETERMINISTIC_MARKERS)


def errors_block_llm_repair(errors: tuple[str, ...], detail: str) -> bool:
    """Return True when LLM repair must not run for these analyzer errors."""
    joined = f"{detail} {' '.join(errors)}".lower()
    return any(marker in joined for marker in _NON_LLM_REPAIRABLE)


def apply_deterministic_analyzer_repairs(result: Any, errors: tuple[str, ...]) -> bool:
    """Apply structural reconciles for known deterministic analyzer failures."""
    from figma_flutter_agent.stages.llm_repair.snapshot import (
        _apply_widget_constructor_signature_reconcile,
        _errors_suggest_extracted_widget_drift,
        _errors_suggest_widget_constructor_signature_mismatch,
    )

    changed = False
    if _errors_suggest_widget_constructor_signature_mismatch(errors):
        changed = _apply_widget_constructor_signature_reconcile(result) or changed
    if _errors_suggest_extracted_widget_drift(errors):
        return changed
    return changed
