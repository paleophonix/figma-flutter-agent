"""Archetype reconcile retirement policy (Track T / T3d)."""

from __future__ import annotations

from figma_flutter_agent.parser.layout.reconcile_registry import (
    ARCHETYPE_RECONCILE_PASS_NAMES,
    should_run_reconcile_pass,
)


def test_archetype_reconcile_passes_off_by_default() -> None:
    for pass_name in ARCHETYPE_RECONCILE_PASS_NAMES:
        assert not should_run_reconcile_pass(pass_name, archetype_reconcile=False)


def test_core_reconcile_passes_always_on() -> None:
    assert should_run_reconcile_pass("reconcile_stack_placements_in_tree", archetype_reconcile=False)
