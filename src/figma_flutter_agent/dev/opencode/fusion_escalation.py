"""Round-based OpenRouter Fusion panel growth from outer correction round 2."""

from __future__ import annotations

from figma_flutter_agent.config.debug_pipeline import (
    FUSION_ESCALATION_MAX_PANEL,
    FUSION_ESCALATION_START_ROUND,
)


def build_escalation_panel(
    base_model: str,
    board_models: tuple[str, ...],
    outer_round: int,
    *,
    max_panel_size: int = FUSION_ESCALATION_MAX_PANEL,
    start_round: int = FUSION_ESCALATION_START_ROUND,
) -> tuple[str, ...]:
    """Build Fusion ``analysis_models`` for one escalation round.

    Round 1 is single-model only (caller should not invoke Fusion). From round
    ``start_round`` the panel grows by one distinct slug per round until
    ``max_panel_size``: base step model first, then ``board_models`` in order.

    Args:
        base_model: Resolved per-step slug (also used as Fusion judge).
        board_models: Ordered escalation pool from agent YAML.
        outer_round: Current outer correction loop index (1-based).
        max_panel_size: Maximum panelists including ``base_model``.
        start_round: First round that uses Fusion escalation.

    Returns:
        Deduped ordered panel capped at ``min(outer_round, max_panel_size)``.

    Raises:
        ValueError: When ``outer_round`` is below ``start_round`` or panel is empty.
    """
    if outer_round < start_round:
        msg = f"escalation panel requires outer_round>={start_round}, got {outer_round}"
        raise ValueError(msg)
    ordered: list[str] = []
    for slug in (base_model.strip(), *board_models):
        normalized = slug.strip()
        if not normalized or normalized in ordered:
            continue
        ordered.append(normalized)
    target_size = min(max(outer_round, start_round), max_panel_size)
    panel = tuple(ordered[:target_size])
    if not panel:
        msg = "escalation panel is empty"
        raise ValueError(msg)
    return panel
