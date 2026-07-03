"""Stage worker hard deadline tests (Program 10 P1-a)."""

from __future__ import annotations

import time

import pytest

from figma_flutter_agent.generator.planner.stage_worker import run_with_spawn_deadline


def _return_42() -> int:
    return 42


def _sleep_long() -> None:
    time.sleep(30)


def test_spawn_worker_returns_result() -> None:
    assert run_with_spawn_deadline(_return_42, timeout_sec=5.0, stage_name="trivial") == 42


def test_spawn_worker_times_out() -> None:
    with pytest.raises(TimeoutError, match="hard deadline"):
        run_with_spawn_deadline(_sleep_long, timeout_sec=0.2, stage_name="hang")
