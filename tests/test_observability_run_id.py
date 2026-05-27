"""Tests for pipeline run correlation ids."""

from __future__ import annotations

from figma_flutter_agent.observability import new_run_id


def test_new_run_id_is_twelve_hex_chars() -> None:
    run_id = new_run_id()
    assert len(run_id) == 12
    assert run_id.isalnum()
