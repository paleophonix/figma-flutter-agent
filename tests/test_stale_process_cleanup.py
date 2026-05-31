"""Tests for stale AST sidecar process cleanup."""

from __future__ import annotations

from figma_flutter_agent.tools.stale_process_cleanup import cleanup_stale_agent_processes


def test_cleanup_skipped_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("FIGMA_FLUTTER_SKIP_STALE_CLEANUP", "1")
    assert cleanup_stale_agent_processes(log=False) == 0
