"""Archetype compensation policy under pixel fidelity profile (Wave F / F0)."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.config.profiles import (
    apply_pixel_fidelity_profile,
    apply_production_profile,
)
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.generator.normalize import (
    normalize_clean_tree,
    reconcile_layout_tree,
)
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
        "figma_flutter_agent.parser.layout.reconcile_cta_footer_surfaces_in_tree",
    ) as archetype_mock:
        reconcile_layout_tree(root, archetype_reconcile=False)
    archetype_mock.assert_not_called()


def test_core_reconcile_runs_weekday_without_archetype_flag() -> None:
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
        reconcile_layout_tree(root, archetype_reconcile=False)
    weekday_mock.assert_called_once()


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
        "figma_flutter_agent.parser.layout.reconcile_cta_footer_surfaces_in_tree",
    ) as archetype_mock:
        reconcile_layout_tree(root, archetype_reconcile=False)
    archetype_mock.assert_not_called()


def test_archetype_reconcile_opt_in_runs_legacy_passes() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[],
    )
    with patch(
        "figma_flutter_agent.parser.layout.reconcile_cta_footer_surfaces_in_tree",
        side_effect=lambda node: node,
    ) as archetype_mock:
        reconcile_layout_tree(root, archetype_reconcile=True)
    archetype_mock.assert_called_once()


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


def test_render_layout_file_default_skips_archetype_reconcile() -> None:
    from figma_flutter_agent.generator.layout.file import render_layout_file

    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[],
    )
    with patch(
        "figma_flutter_agent.generator.normalize.reconcile_layout_tree",
        side_effect=lambda tree, **kwargs: tree,
    ) as reconcile_mock:
        render_layout_file(root, feature_name="screen", uses_svg=False)
    reconcile_mock.assert_called_once()
    assert reconcile_mock.call_args.kwargs.get("archetype_reconcile") is False


def test_destination_trees_receive_archetype_reconcile_from_config() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "figma_flutter_agent"
        / "generator"
        / "planner"
        / "plan.py"
    )
    text = source.read_text(encoding="utf-8")
    dest_idx = text.index(
        "context.destination_trees[route_name] = normalize_clean_tree"
    )
    dest_block = text[dest_idx : dest_idx + 700]
    assert "archetype_reconcile=generation_cfg.archetype_reconcile" in dest_block
