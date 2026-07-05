"""GenerationPlanContext dataclass and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from figma_flutter_agent.compiler.m3_policy import DEFAULT_M3_POLICY, M3Policy
from figma_flutter_agent.config import Settings
from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    FontManifest,
    NodeType,
)


def _resolve_use_scaffold(settings: Settings, clean_tree: CleanDesignTreeNode) -> bool:
    """Classic absolute frames are full-bleed; skip Material AppBar unless forced in YAML."""
    if not settings.agent.layout.use_scaffold:
        return False
    return clean_tree.type != NodeType.STACK


def _tree_has_layout_slots(root: CleanDesignTreeNode) -> bool:
    """Return True when any node in ``root`` carries a geometry ``layout_slot``."""
    stack = [root]
    while stack:
        node = stack.pop()
        if node.layout_slot is not None:
            return True
        stack.extend(node.children)
    return False


@dataclass
class GenerationPlanContext:
    """Inputs required to plan generated Dart files without writing them."""

    settings: Settings
    clean_tree: CleanDesignTreeNode
    tokens: DesignTokens
    resolved_feature: str
    node_id: str
    cluster_summary: dict[str, int]
    asset_manifest: AssetManifest = field(default_factory=AssetManifest)
    font_manifest: FontManifest = field(default_factory=FontManifest)
    generation: FlutterGenerationResponse | None = None
    destination_generations: dict[str, FlutterGenerationResponse] = field(default_factory=dict)
    destination_trees: dict[str, CleanDesignTreeNode] = field(default_factory=dict)
    navigation_plan: PrototypeNavigationPlan = field(default_factory=PrototypeNavigationPlan)
    figma_root: dict[str, Any] = field(default_factory=dict)
    routing_on: bool = False
    package_name: str = "demo_app"
    blocked_asset_paths: frozenset[str] = field(default_factory=frozenset)
    skip_screen_post_reconcile: bool = False
    skip_final_reconcile: bool = False
    project_dir: Path | None = None
    truth_snapshot: CleanDesignTreeNode | None = None
    truth_emit_pair: object | None = None
    reusable_candidates: list[Any] = field(default_factory=list)
    llm_client_factory: Any | None = None
    m3_policy: M3Policy = field(default_factory=lambda: DEFAULT_M3_POLICY)
    cluster_classes: dict[str, str] | None = None
    cluster_widget_specs: list[Any] = field(default_factory=list)
