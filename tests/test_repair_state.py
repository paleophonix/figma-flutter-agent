"""Tests for repair step resume routing helpers."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.repair_state import repair_needs_retry


def test_repair_needs_retry_provider_error() -> None:
    assert repair_needs_retry(
        {"provider_error": "Aborted", "noop": False, "filesTouched": []},
    )


def test_repair_needs_retry_timed_out() -> None:
    assert repair_needs_retry({"timed_out": True, "filesTouched": []})


def test_repair_needs_retry_false_when_files_touched() -> None:
    assert not repair_needs_retry({"filesTouched": ["planned_files/foo.py"]})


def test_repair_needs_retry_false_when_noop() -> None:
    assert not repair_needs_retry({"noop": True, "provider_error": "Aborted"})


def test_repair_needs_retry_false_when_gates_passed() -> None:
    assert not repair_needs_retry({"filesTouched": [], "gates": {"passed": True}})
