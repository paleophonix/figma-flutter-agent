"""Tests for failure class routing."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.failure_class import (
    FailureClass,
    classify_check_route,
    same_root_hash,
)


def test_classify_patch_code_emit_routes_fix() -> None:
    assert classify_check_route(FailureClass.PATCH_CODE_EMIT) == "fix"


def test_same_root_hash_stable() -> None:
    a = same_root_hash(failure_class="PATCH_CODE_EMIT", law_id="law_a", owning_layer="emit")
    b = same_root_hash(failure_class="PATCH_CODE_EMIT", law_id="law_a", owning_layer="emit")
    assert a == b
