"""Archetype compensation policy under pixel fidelity profile (Wave F / F0)."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.config.profiles import (
    apply_pixel_fidelity_profile,
    apply_production_profile,
)
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.generator.normalize import normalize_clean_tree, reconcile_layout_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_pixel_profile_suppresses_archetype_reconcile() -> None:
    settings = apply_pixel_fidelity_profile(Settings())
    assert settings.agent.generation.suppress_archetype_compensation is True
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[],
    )
    with patch(
        "figma_flutter_agent.parser.layout.reconcile_weekday_chip_row_in_tree",
    ) as weekday_mock:
        reconcile_layout_tree(root, archetype_reconcile=False)
    weekday_mock.assert_not_called()


def test_pixel_profile_enables_de_archetype_pass() -> None:
    settings = apply_pixel_fidelity_profile(Settings())
    assert settings.agent.runtime.de_archetype_pass is True


def test_default_profile_skips_archetype_reconcile_by_default() -> None:
    settings = apply_production_profile(Settings())
    assert settings.agent.generation.archetype_reconcile is False
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[],
    )
    with patch(
        "figma_flutter_agent.parser.layout.reconcile_weekday_chip_row_in_tree",
    ) as weekday_mock:
        reconcile_layout_tree(root, archetype_reconcile=False)
    weekday_mock.assert_not_called()


def test_archetype_reconcile_opt_in_runs_legacy_passes() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[],
    )
    with patch(
        "figma_flutter_agent.parser.layout.reconcile_weekday_chip_row_in_tree",
        side_effect=lambda node: node,
    ) as weekday_mock:
        reconcile_layout_tree(root, archetype_reconcile=True)
    weekday_mock.assert_called_once()

def test_normalize_clean_tree_skips_product_hero_when_suppressed() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[],
    )
    with patch(
        "figma_flutter_agent.parser.layout.reconcile_product_hero_photo_viewport_in_tree",
    ) as hero_mock:
        normalize_clean_tree(
            root,
            apply_render_safety=False,
            use_geometry_planner=False,
            suppress_archetype_compensation=True,
        )
    hero_mock.assert_not_called()
