"""Repair stage data models — request/result dataclasses."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.llm.clients import LlmClient
from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FontManifest,
)
from figma_flutter_agent.stages.llm import LlmStageResult


@dataclass
class LlmRepairStageRequest:
    """Inputs for post-generation LLM repair and visual refine loops."""

    settings: Settings
    dry_run: bool
    project_dir: Path
    planned_files: dict[str, str]
    llm_result: LlmStageResult
    clean_tree: CleanDesignTreeNode
    tokens: DesignTokens
    resolved_feature: str
    node_id: str
    cluster_summary: dict[str, int]
    asset_manifest: AssetManifest
    font_manifest: FontManifest
    widget_hints: list[str]
    navigation_hints: list[str]
    routing_on: bool
    navigation_plan: PrototypeNavigationPlan
    figma_root: dict[str, Any]
    package_name: str
    blocked_asset_paths: frozenset[str] = field(default_factory=frozenset)
    destination_trees: dict[str, CleanDesignTreeNode] = field(default_factory=dict)
    llm_client_factory: Callable[[Settings], LlmClient] | None = None
    llm_refine_client_factory: Callable[[Settings], LlmClient] | None = None
    figma_reference_png: bytes | None = None


@dataclass
class LlmRepairStageResult:
    """Output of the analyze repair loop."""

    planned_files: dict[str, str]
    llm_result: LlmStageResult
    warnings: list[str] = field(default_factory=list)
    repair_attempts: int = 0
