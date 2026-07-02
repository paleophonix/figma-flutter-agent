"""Planner substage timing helpers."""

from __future__ import annotations

import time

from loguru import logger


def plan_substage_start(label: str) -> float:
    """Log planner substage start and return a monotonic timestamp."""
    logger.info("plan: {} started", label)
    return time.monotonic()


def plan_substage_done(label: str, started: float) -> None:
    """Log planner substage completion duration."""
    logger.info("plan: {} finished in {:.2f}s", label, time.monotonic() - started)
