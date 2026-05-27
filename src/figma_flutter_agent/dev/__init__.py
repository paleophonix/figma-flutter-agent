"""Dev run helpers for figma-flutter-agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["RunScreenPlan", "plan_run_screen", "run_screen_blocking"]

if TYPE_CHECKING:
    from figma_flutter_agent.dev.run import RunScreenPlan, plan_run_screen, run_screen_blocking


def __getattr__(name: str) -> object:
    if name in __all__:
        from figma_flutter_agent.dev import run as _run

        return getattr(_run, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
