"""Registry of layout reconcile passes by compensation tier."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from figma_flutter_agent.schemas import CleanDesignTreeNode

ReconcileTier = Literal["core", "archetype"]

CORE_RECONCILE_PASS_NAMES: frozenset[str] = frozenset(
    {
        "reconcile_stack_placements_in_tree",
        "reconcile_render_bounds_expansion_in_tree",
        "reconcile_weekday_chip_row_in_tree",
        "reconcile_checkout_footer_bottom_nav_in_tree",
    }
)

ARCHETYPE_RECONCILE_PASS_NAMES: frozenset[str] = frozenset(
    {
        "reconcile_auth_button_icon_placements_in_tree",
        "reconcile_promo_card_row_tops_in_tree",
        "reconcile_grid_child_visual_order_in_tree",
        "reconcile_duplicate_product_card_grids_in_tree",
        "reconcile_cta_footer_surfaces_in_tree",
        "reconcile_logo_wordmark_top_in_tree",
        "reconcile_title_subtitle_stacks_in_tree",
        "reconcile_consent_checkbox_rows_in_tree",
        "reconcile_payment_selection_state_in_tree",
        "reconcile_centered_text_placements_in_tree",
        "reconcile_playback_timestamp_row_in_tree",
        "reconcile_product_hero_photo_viewport_in_tree",
    }
)


def reconcile_pass_tier(pass_name: str) -> ReconcileTier:
    """Return the compensation tier for a reconcile pass name."""
    if pass_name in CORE_RECONCILE_PASS_NAMES:
        return "core"
    if pass_name in ARCHETYPE_RECONCILE_PASS_NAMES:
        return "archetype"
    msg = f"Unknown reconcile pass: {pass_name!r}"
    raise ValueError(msg)


def should_run_reconcile_pass(pass_name: str, *, archetype_reconcile: bool) -> bool:
    """Return whether a reconcile pass should run under the current policy."""
    tier = reconcile_pass_tier(pass_name)
    if tier == "core":
        return True
    return archetype_reconcile


def run_registered_reconcile_passes(
    tree: CleanDesignTreeNode,
    *,
    archetype_reconcile: bool,
    allow_placement_clamp: bool,
) -> CleanDesignTreeNode:
    """Run core and optional archetype reconcile passes in registry order."""
    from figma_flutter_agent.parser.layout import (
        reconcile_auth_button_icon_placements_in_tree,
        reconcile_centered_text_placements_in_tree,
        reconcile_checkout_footer_bottom_nav_in_tree,
        reconcile_consent_checkbox_rows_in_tree,
        reconcile_cta_footer_surfaces_in_tree,
        reconcile_duplicate_product_card_grids_in_tree,
        reconcile_grid_child_visual_order_in_tree,
        reconcile_logo_wordmark_top_in_tree,
        reconcile_payment_selection_state_in_tree,
        reconcile_playback_timestamp_row_in_tree,
        reconcile_promo_card_row_tops_in_tree,
        reconcile_stack_placements_in_tree,
        reconcile_title_subtitle_stacks_in_tree,
        reconcile_weekday_chip_row_in_tree,
    )
    from figma_flutter_agent.parser.render_bounds import (
        reconcile_render_bounds_expansion_in_tree,
    )

    passes: list[tuple[str, Callable[[CleanDesignTreeNode], CleanDesignTreeNode]]] = [
        (
            "reconcile_stack_placements_in_tree",
            lambda node: reconcile_stack_placements_in_tree(
                node,
                allow_clamp=allow_placement_clamp,
            ),
        ),
        (
            "reconcile_render_bounds_expansion_in_tree",
            reconcile_render_bounds_expansion_in_tree,
        ),
        (
            "reconcile_weekday_chip_row_in_tree",
            reconcile_weekday_chip_row_in_tree,
        ),
        (
            "reconcile_checkout_footer_bottom_nav_in_tree",
            reconcile_checkout_footer_bottom_nav_in_tree,
        ),
    ]

    if archetype_reconcile:
        passes.extend(
            [
                (
                    "reconcile_auth_button_icon_placements_in_tree",
                    reconcile_auth_button_icon_placements_in_tree,
                ),
                (
                    "reconcile_promo_card_row_tops_in_tree",
                    reconcile_promo_card_row_tops_in_tree,
                ),
                (
                    "reconcile_grid_child_visual_order_in_tree",
                    reconcile_grid_child_visual_order_in_tree,
                ),
                (
                    "reconcile_duplicate_product_card_grids_in_tree",
                    reconcile_duplicate_product_card_grids_in_tree,
                ),
                (
                    "reconcile_cta_footer_surfaces_in_tree",
                    reconcile_cta_footer_surfaces_in_tree,
                ),
                (
                    "reconcile_logo_wordmark_top_in_tree",
                    reconcile_logo_wordmark_top_in_tree,
                ),
                (
                    "reconcile_title_subtitle_stacks_in_tree",
                    reconcile_title_subtitle_stacks_in_tree,
                ),
                (
                    "reconcile_consent_checkbox_rows_in_tree",
                    reconcile_consent_checkbox_rows_in_tree,
                ),
                (
                    "reconcile_payment_selection_state_in_tree",
                    reconcile_payment_selection_state_in_tree,
                ),
                (
                    "reconcile_centered_text_placements_in_tree",
                    reconcile_centered_text_placements_in_tree,
                ),
                (
                    "reconcile_playback_timestamp_row_in_tree",
                    reconcile_playback_timestamp_row_in_tree,
                ),
            ]
        )

    working = tree
    for pass_name, pass_fn in passes:
        if should_run_reconcile_pass(pass_name, archetype_reconcile=archetype_reconcile):
            working = pass_fn(working)
    return working
