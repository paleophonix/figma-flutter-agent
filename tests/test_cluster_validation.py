"""Hard gates for duplicate structural cluster extraction."""

import json
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.planner import plan_from_figma_root
from figma_flutter_agent.generator.widget_validation import validate_cluster_widget_extraction
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.stages.validate import ValidateStageRequest, validate_planned_generation


def test_catalog_nested_cluster_widgets_use_const_refs_in_parent() -> None:
    root = json.loads(Path("tests/fixtures/figma_cards_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"])

    card_source = planned["lib/widgets/product_card_widget.dart"]
    assert "Semantics(label: 'Title'" in card_source
    assert "const TitleWidget()" not in card_source


def test_catalog_passes_duplicate_cluster_gate() -> None:
    root = json.loads(Path("tests/fixtures/figma_cards_sample.json").read_text(encoding="utf-8"))
    settings = Settings()
    tree, _, _, cluster_summary = build_clean_tree(root)
    planned = plan_from_figma_root(root, settings, node_id=root["id"])

    validate_cluster_widget_extraction(
        planned,
        [tree],
        cluster_summary,
        min_count=settings.agent.generation.cluster_min_count,
        widget_suffix=settings.agent.naming.widget_suffix,
        enforce_cluster_widgets=True,
        fail_duplicate_clusters=True,
    )


def test_duplicate_cluster_gate_fails_without_widget_file() -> None:
    card = CleanDesignTreeNode(
        id="1:1",
        name="Card",
        type=NodeType.CARD,
        cluster_id="cluster_0",
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[card, card],
    )
    cluster_summary = {"cluster_0": 2}
    planned = {
        "lib/generated/screen_layout.dart": "const Placeholder()",
    }

    with pytest.raises(GenerationError, match="requires widget"):
        validate_cluster_widget_extraction(
            planned,
            [root],
            cluster_summary,
            min_count=2,
            widget_suffix="Widget",
            enforce_cluster_widgets=True,
            fail_duplicate_clusters=True,
        )


def test_duplicate_cluster_gate_fails_when_layout_inlines_duplicates() -> None:
    card = CleanDesignTreeNode(
        id="1:1",
        name="Product Card",
        type=NodeType.CARD,
        cluster_id="cluster_0",
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[card, card, card],
    )
    cluster_summary = {"cluster_0": 3}
    planned = {
        "lib/widgets/product_card_widget.dart": "class ProductCardWidget {}",
        "lib/generated/catalog_layout.dart": ("Column(children: [Text('inline'), Text('inline')])"),
    }

    with pytest.raises(GenerationError, match="only 0 reference"):
        validate_cluster_widget_extraction(
            planned,
            [root],
            cluster_summary,
            min_count=2,
            widget_suffix="Widget",
            enforce_cluster_widgets=True,
            fail_duplicate_clusters=True,
        )


def test_validate_stage_enables_cluster_gate_from_settings() -> None:
    root = json.loads(Path("tests/fixtures/figma_cards_sample.json").read_text(encoding="utf-8"))
    agent = Settings().agent.model_copy(
        update={
            "quality": Settings().agent.quality.model_copy(update={"fail_duplicate_clusters": True})
        }
    )
    settings = Settings().model_copy(update={"agent": agent})
    planned = plan_from_figma_root(root, settings, node_id=root["id"])
    tree, _, _, cluster_summary = build_clean_tree(root)

    validate_planned_generation(
        ValidateStageRequest(
            planned_files=planned,
            clean_trees=[tree],
            responsive_enabled=settings.agent.responsive.enabled,
            avoid_fixed_sizes=settings.agent.layout.avoid_fixed_sizes,
            cluster_summary=cluster_summary,
            cluster_min_count=settings.agent.generation.cluster_min_count,
            widget_suffix=settings.agent.naming.widget_suffix,
            enforce_cluster_widgets=settings.agent.generation.enforce_cluster_widgets,
            fail_duplicate_clusters=settings.agent.quality.fail_duplicate_clusters,
        )
    )
