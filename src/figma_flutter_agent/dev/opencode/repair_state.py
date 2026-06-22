"""Repair step outcome helpers for resume routing."""

from __future__ import annotations

from typing import Any


def repair_needs_retry(repair: dict[str, Any] | None) -> bool:
    """Return whether an incomplete repair pass should rerun OpenCode.

    Args:
        repair: Persisted ``repair`` step payload from the reasoning chain.

    Returns:
        True when the repair session failed before producing compiler edits.
    """
    if not isinstance(repair, dict) or repair.get("skipped"):
        return False
    if repair.get("noop"):
        return False
    if repair.get("provider_error") or repair.get("timed_out"):
        return True
    touched = repair.get("filesTouched")
    if isinstance(touched, list) and touched:
        return False
    gates = repair.get("gates")
    if isinstance(gates, dict) and gates.get("passed"):
        return False
    if repair.get("blocked"):
        return False
    return True
