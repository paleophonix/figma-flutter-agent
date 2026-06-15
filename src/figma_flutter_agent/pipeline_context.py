"""Mutable state carried through the generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from figma_flutter_agent.parser.truth_snapshot import TruthEmitPair

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import PipelineError
from figma_flutter_agent.figma.url import ParsedFigmaUrl
from figma_flutter_agent.parser.accessibility import (
    apply_accessibility_fixes,
    collect_accessibility_warnings,
    enforce_contrast_gates,
)
from figma_flutter_agent.parser.dedup.instances import DedupResult
from figma_flutter_agent.parser.prototype import PrototypeLink
from figma_flutter_agent.parser.transitions import PrototypeTransition
from figma_flutter_agent.parser.ux import collect_ux_suggestions, enforce_ux_gates
from figma_flutter_agent.parser.ux_report import write_analysis_reports
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FontManifest,
)

if TYPE_CHECKING:
    pass
from figma_flutter_agent.stages.fetch import FigmaFetchResult
from figma_flutter_agent.stages.parse import FigmaParseResult
from figma_flutter_agent.validation.reference import collect_layout_metric_warnings


@dataclass
class PipelineContext:
    """Aggregated fetch/parse/plan state for ``run_pipeline``."""

    settings: Settings
    project_dir: Path
    parsed: ParsedFigmaUrl
    dry_run: bool
    verbose: bool
    resolved_sync: bool
    feature_name: str | None
    regenerate_templates: bool

    figma_root: dict[str, Any] = field(default_factory=dict)
    prototype_links: list[PrototypeLink] = field(default_factory=list)
    frame_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    image_fill_urls: dict[str, str] = field(default_factory=dict)
    published_styles: dict[str, dict[str, Any]] = field(default_factory=dict)
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    component_sets: dict[str, dict[str, Any]] = field(default_factory=dict)
    style_paint_index: dict[str, dict[str, Any]] = field(default_factory=dict)

    tokens: DesignTokens | None = None
    clean_tree: CleanDesignTreeNode | None = None
    truth_snapshot: CleanDesignTreeNode | None = None
    truth_emit_pair: TruthEmitPair | None = None
    absolute_ratio: float = 0.0
    dedup_result: DedupResult | None = None
    cluster_summary: dict[str, int] = field(default_factory=dict)
    destination_trees: dict[str, CleanDesignTreeNode] = field(default_factory=dict)
    destination_widget_hints: dict[str, list[str]] = field(default_factory=dict)
    asset_manifest: AssetManifest = field(default_factory=AssetManifest)
    font_manifest: FontManifest = field(default_factory=FontManifest)
    blocked_asset_paths: frozenset[str] = field(default_factory=frozenset)
    reference_image_hash: str | None = None
    reference_image_png: bytes | None = None

    resolved_feature: str = ""
    warnings: list[str] = field(default_factory=list)

    def apply_fetch(self, fetch: FigmaFetchResult) -> None:
        """Store raw fetch payload on the context."""
        self.figma_root = fetch.root
        self.prototype_links = fetch.prototype_links
        self.frame_index = fetch.frame_index
        self.published_styles = fetch.published_styles
        self.components = fetch.components
        self.component_sets = fetch.component_sets
        self.style_paint_index = fetch.style_paint_index
        self.image_fill_urls = fetch.image_fill_urls

    def apply_parse(self, parsed_frame: FigmaParseResult) -> None:
        """Store parse-stage outputs on the context."""
        from figma_flutter_agent.parser.truth_snapshot import capture_truth_snapshot

        self.tokens = parsed_frame.tokens
        self.clean_tree = parsed_frame.clean_tree
        if parsed_frame.clean_tree is not None:
            self.truth_snapshot = capture_truth_snapshot(parsed_frame.clean_tree)
        self.absolute_ratio = parsed_frame.absolute_ratio
        self.dedup_result = parsed_frame.dedup_result
        self.cluster_summary = parsed_frame.cluster_summary
        self.destination_trees = parsed_frame.destination_trees
        self.destination_widget_hints = parsed_frame.destination_widget_hints

    def enforce_accessibility_gates(self) -> None:
        """Run hard accessibility gates on the parse tree before optional auto-fixes."""
        if self.clean_tree is None:
            return
        if self.settings.agent.quality.strict_contrast:
            enforce_contrast_gates(self.clean_tree)
            for destination_tree in self.destination_trees.values():
                enforce_contrast_gates(destination_tree)

    def apply_accessibility_fixes(self) -> None:
        """Run optional clean-tree accessibility fixes."""
        if not self.settings.agent.accessibility.auto_fix or self.clean_tree is None:
            return
        self.clean_tree = apply_accessibility_fixes(self.clean_tree)
        self.destination_trees = {
            node_id: apply_accessibility_fixes(tree)
            for node_id, tree in self.destination_trees.items()
        }

    def collect_analysis_warnings(
        self,
        *,
        animation_warnings: list[str] | None = None,
    ) -> None:
        """Append layout, accessibility, and UX warnings (and optional hard gates)."""
        if self.clean_tree is None:
            return
        if self.figma_root:
            self.warnings.extend(
                collect_layout_metric_warnings(
                    self.figma_root,
                    max_web_width=self.settings.agent.responsive.max_web_width,
                )
            )
        if self.absolute_ratio > 0.3:
            self.warnings.append(
                "More than 30% of nodes use absolute positioning; responsive quality may degrade."
            )
        self.warnings.extend(collect_accessibility_warnings(self.clean_tree))
        for destination_tree in self.destination_trees.values():
            self.warnings.extend(collect_accessibility_warnings(destination_tree))
            if self.settings.agent.ux.suggestions:
                self.warnings.extend(collect_ux_suggestions(destination_tree))
        if self.settings.agent.ux.suggestions:
            self.warnings.extend(collect_ux_suggestions(self.clean_tree))
        if animation_warnings:
            self.warnings.extend(animation_warnings)
        if self.settings.agent.quality.enforce_spec9_gates:
            enforce_ux_gates(
                self.clean_tree,
                max_layout_depth=self.settings.agent.quality.max_layout_depth,
            )
            for destination_tree in self.destination_trees.values():
                enforce_ux_gates(
                    destination_tree,
                    max_layout_depth=self.settings.agent.quality.max_layout_depth,
                )

    def persist_optional_reports(
        self,
        *,
        feature_slug: str,
        route_transitions: dict[str, PrototypeTransition] | None = None,
        routing_type: str = "none",
    ) -> None:
        """Write AI UX / animation JSON reports when enabled in agent config."""
        if self.clean_tree is None or self.dry_run:
            return
        agent = self.settings.agent
        if not agent.ux.write_report and not agent.animations.write_manifest:
            return
        write_analysis_reports(
            self.project_dir,
            feature_slug=feature_slug,
            root=self.clean_tree,
            prototype_links=self.prototype_links,
            route_transitions=route_transitions,
            routing_type=routing_type,
            dark_mode_enabled=agent.dark_mode.enabled,
            write_ux_report=agent.ux.write_report,
            write_animation_manifest=agent.animations.write_manifest,
        )

    def require_parse_complete(self) -> None:
        """Raise when parse outputs are missing."""
        if self.tokens is None or self.clean_tree is None or self.dedup_result is None:
            raise PipelineError("Pipeline parse stage did not produce tokens or clean tree")
