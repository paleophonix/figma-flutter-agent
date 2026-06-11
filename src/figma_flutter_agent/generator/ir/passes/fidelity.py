"""Backward-compatible facade for fidelity tier stamping (EPIC 4.5)."""

from figma_flutter_agent.generator.ir.fidelity.stamp import (
    downgrade_node_tier,
    stamp_fidelity_tiers,
)

__all__ = ["downgrade_node_tier", "stamp_fidelity_tiers"]
