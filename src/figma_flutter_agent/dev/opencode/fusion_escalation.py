"""Correction-cycle-based OpenRouter Fusion panel sizing."""

from __future__ import annotations

from figma_flutter_agent.config.debug_pipeline import (
    DEFAULT_MAX_BOARD_MODELS,
    DEFAULT_MIN_BOARD_MODELS,
    FUSION_DISABLED_MIN_BOARD_MODELS,
)


def build_escalation_panel(
    base_model: str,
    board_models: tuple[str, ...],
    outer_round: int,
    *,
    min_panel_size: int = DEFAULT_MIN_BOARD_MODELS,
    max_panel_size: int = DEFAULT_MAX_BOARD_MODELS,
) -> tuple[str, ...]:
    """Build Fusion ``analysis_models`` for one correction cycle.

    Call only when ``min_panel_size > 1`` (Fusion enabled). Panel size is
    ``min(max(outer_round, min_panel_size), max_panel_size)``: base step model
    first, then ``board_models`` in order.

    Args:
        base_model: Resolved per-step slug (also used as Fusion judge).
        board_models: Ordered escalation pool from agent YAML.
        outer_round: Current outer correction loop index (1-based).
        min_panel_size: Floor on panel size (``debug_pipeline.min_board_models``).
        max_panel_size: Ceiling on panel size (``debug_pipeline.max_board_models``).

    Returns:
        Deduped ordered panel capped between ``min_panel_size`` and
        ``max_panel_size``.

    Raises:
        ValueError: When Fusion is disabled, ``outer_round`` is invalid, or panel
            is empty.
    """
    if min_panel_size <= FUSION_DISABLED_MIN_BOARD_MODELS:
        msg = (
            "escalation panel requires min_panel_size>=2 when Fusion is enabled "
            f"(got {min_panel_size})"
        )
        raise ValueError(msg)
    if outer_round < 1:
        msg = f"escalation panel requires outer_round>=1, got {outer_round}"
        raise ValueError(msg)
    ordered: list[str] = []
    for slug in (base_model.strip(), *board_models):
        normalized = slug.strip()
        if not normalized or normalized in ordered:
            continue
        ordered.append(normalized)
    growth_target = max(outer_round, min_panel_size)
    target_size = min(growth_target, max_panel_size)
    panel = tuple(ordered[:target_size])
    if not panel:
        msg = "escalation panel is empty"
        raise ValueError(msg)
    return panel
