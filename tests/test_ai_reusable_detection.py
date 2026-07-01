"""AI-assisted reusable widget detection tests."""

from __future__ import annotations

from figma_flutter_agent.config.models import AiReusableConfig, WidgetExtractionConfig
from figma_flutter_agent.generator.widget_extraction import collect_widget_specs
from figma_flutter_agent.generator.widget_extraction.enrich import apply_widget_enrich_response
from figma_flutter_agent.generator.widget_extraction.gates import gate_reusable_candidate
from figma_flutter_agent.generator.widget_extraction.scorer import score_static_candidates
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec
from figma_flutter_agent.llm.reusable_candidates import build_ai_reusable_hints
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing
from figma_flutter_agent.schemas.reusable_candidates import (
    ReusableWidgetCandidate,
    ReusableWidgetEvidence,
    WidgetEnrichEntry,
    WidgetEnrichResponse,
)


def _card_node(card_id: str, *, title: str) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=card_id,
        name="Product Card",
        type=NodeType.CARD,
        sizing=Sizing(width=200.0, height=250.0),
        children=[
            CleanDesignTreeNode(
                id=f"{card_id}:image",
                name="Image",
                type=NodeType.IMAGE,
                sizing=Sizing(width=180.0, height=120.0),
            ),
            CleanDesignTreeNode(
                id=f"{card_id}:title",
                name="Title",
                type=NodeType.TEXT,
                text=title,
                sizing=Sizing(width=160.0, height=24.0),
            ),
        ],
    )


def _screen_with_cards(*cards: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=list(cards),
    )


def test_static_scorer_finds_shape_repeat() -> None:
    screen = _screen_with_cards(
        _card_node("card-1", title="A"),
        _card_node("card-2", title="B"),
        _card_node("card-3", title="C"),
    )
    config = WidgetExtractionConfig(policy="auto_reusable", min_count=2)
    scored = score_static_candidates(screen, config=config)
    assert scored
    assert scored[0].score >= config.auto_reusable_min_score
    assert len(scored[0].similar_node_ids) >= 2


def test_static_scorer_skips_trivial_text() -> None:
    screen = CleanDesignTreeNode(
        id="screen",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="text-1",
                name="Label",
                type=NodeType.TEXT,
                text="Hello",
                sizing=Sizing(width=80.0, height=20.0),
            )
        ],
    )
    config = WidgetExtractionConfig(policy="auto_reusable")
    assert score_static_candidates(screen, config=config) == []


def test_gates_reject_low_confidence_llm() -> None:
    screen = _screen_with_cards(_card_node("card-1", title="A"))
    config = WidgetExtractionConfig(
        ai_reusable=AiReusableConfig(enabled=True, min_confidence=0.85, require_static_gate=False),
    )
    candidate = ReusableWidgetCandidate(
        nodeId="card-1",
        widgetName="ProductCard",
        reason="looks reusable",
        confidence=0.5,
    )
    assert (
        gate_reusable_candidate(
            candidate,
            config=config,
            root=screen,
            widget_suffix="Widget",
            claimed_class_names=set(),
            claimed_node_ids=set(),
        )
        is None
    )


def test_suggest_mode_adds_hints_not_specs() -> None:
    screen = _screen_with_cards(
        _card_node("card-1", title="A"),
        _card_node("card-2", title="B"),
    )
    config = WidgetExtractionConfig(
        policy="balanced",
        ai_reusable=AiReusableConfig(
            enabled=True,
            mode="suggest",
            require_static_gate=False,
            require_evidence=False,
        ),
    )
    candidate = ReusableWidgetCandidate(
        nodeId="card-1",
        widgetName="ProductCard",
        reason="card family",
        confidence=0.92,
        evidence=ReusableWidgetEvidence(similarNodes=["card-1", "card-2"]),
    )
    hints = build_ai_reusable_hints(screen, [candidate], config=config, widget_suffix="Widget")
    assert hints
    specs = collect_widget_specs(screen, {}, config=config, llm_candidates=[candidate])
    assert specs == []


def test_enforce_mode_extracts_gated_candidate() -> None:
    screen = _screen_with_cards(
        _card_node("card-1", title="A"),
        _card_node("card-2", title="B"),
        _card_node("card-3", title="C"),
    )
    config = WidgetExtractionConfig(
        policy="balanced",
        min_count=2,
        ai_reusable=AiReusableConfig(
            enabled=True,
            mode="enforce",
            require_static_gate=True,
            require_evidence=True,
        ),
    )
    candidate = ReusableWidgetCandidate(
        nodeId="card-1",
        widgetName="ProductCard",
        reason="repeated cards",
        confidence=0.95,
        evidence=ReusableWidgetEvidence(similarNodes=["card-1", "card-2", "card-3"]),
    )
    specs = collect_widget_specs(screen, {}, config=config, llm_candidates=[candidate])
    assert len(specs) == 1
    assert specs[0].class_name == "ProductCardWidget"


def test_policy_auto_reusable_enables_static_only() -> None:
    screen = _screen_with_cards(
        _card_node("card-1", title="A"),
        _card_node("card-2", title="B"),
        _card_node("card-3", title="C"),
    )
    config = WidgetExtractionConfig(policy="auto_reusable", min_count=2)
    specs = collect_widget_specs(screen, {}, config=config)
    assert len(specs) == 1
    assert specs[0].cluster_id.startswith("semantic_")


def test_enrich_renames_cluster_widget() -> None:
    card = _card_node("card-1", title="A")
    spec = ClusterWidgetSpec(
        cluster_id="cluster_0",
        class_name="Cluster0Widget",
        file_name="cluster0_widget",
        representative=card,
    )
    response = WidgetEnrichResponse(
        entries=[
            WidgetEnrichEntry(
                clusterId="cluster_0",
                widgetName="ProductCardWidget",
                paramRenames={},
            )
        ]
    )
    enriched = apply_widget_enrich_response([spec], response, widget_suffix="Widget")
    assert enriched[0].class_name == "ProductCardWidget"
    assert enriched[0].file_name == "product_card_widget"
