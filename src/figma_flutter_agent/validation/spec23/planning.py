"""Planning helpers and codegen criteria for spec-23."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.generator.planner import GenerationPlanContext, plan_generation_files
from figma_flutter_agent.parser.accessibility import apply_accessibility_fixes
from figma_flutter_agent.parser.tokens.build import build_design_tokens
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse, NodeType
from figma_flutter_agent.validation.spec23.models import Spec23CriterionResult


def _resolve_feature_name(root: dict[str, Any], settings: Settings) -> str:
    configured = settings.agent.naming.feature_name
    if configured != "auto":
        return to_snake_case(configured)
    return to_snake_case(str(root.get("name", "feature")))


def _tree_has_repaint_candidate(tree: CleanDesignTreeNode) -> bool:
    """Return True when the tree contains scrollable or heavy UI subtrees."""

    def walk(node: CleanDesignTreeNode) -> bool:
        if node.scroll_axis != "none":
            return True
        if node.type in {
            NodeType.GRID,
            NodeType.CAROUSEL,
            NodeType.TABS,
            NodeType.BOTTOM_NAV,
        }:
            return True
        return any(walk(child) for child in node.children)

    return walk(tree)


def _criterion_flutter_optimization(
    planned: dict[str, str],
    tree: CleanDesignTreeNode,
    *,
    strict: bool,
) -> Spec23CriterionResult:
    layout_sources = "\n".join(
        content for path, content in planned.items() if path.endswith("_layout.dart")
    )
    if not strict:
        passed = "RepaintBoundary" in layout_sources or not _tree_has_repaint_candidate(tree)
        return Spec23CriterionResult(
            name="flutter_optimization",
            passed=passed,
            detail="optional",
        )
    needs_boundary = _tree_has_repaint_candidate(tree)
    has_boundary = "RepaintBoundary" in layout_sources
    passed = has_boundary if needs_boundary else True
    detail = "repaint" if needs_boundary else "n/a"
    return Spec23CriterionResult(name="flutter_optimization", passed=passed, detail=detail)


def _criterion_responsive_layouts(
    planned: dict[str, str], *, strict: bool
) -> Spec23CriterionResult:
    layout_source = planned.get("lib/theme/app_layout.dart", "")
    if strict:
        passed = (
            "mobileSmallMax = 480" in layout_source
            and "mobileLargeMax = 768" in layout_source
            and "tabletMax = 1024" in layout_source
            and "isMobileSmall(double width)" in layout_source
            and "isMobileLarge(double width)" in layout_source
            and "isTablet(double width)" in layout_source
            and "isDesktop(double width) => width > tabletMax" in layout_source
            and "isWideLayout(double width)" in layout_source
        )
        detail = "spec 7.3 breakpoints (480/768/1024) + wide layout reflow"
    else:
        passed = "AppBreakpoints" in layout_source
        detail = ""
    return Spec23CriterionResult(name="responsive_layouts", passed=passed, detail=detail)


def _plan_for_spec23(
    root: dict[str, Any],
    settings: Settings,
    *,
    node_id: str,
    package_name: str,
    generation: FlutterGenerationResponse | None = None,
) -> tuple[dict[str, str], CleanDesignTreeNode]:
    """Plan generated Dart for spec-23 evaluation."""
    tokens = build_design_tokens(root, None)
    tree, _, _, cluster_summary = build_clean_tree(root)
    if generation is None:
        from figma_flutter_agent.generator.ir.tree import default_screen_ir

        generation = FlutterGenerationResponse(screen_ir=default_screen_ir(tree))
    if settings.agent.accessibility.auto_fix:
        tree = apply_accessibility_fixes(tree)
    resolved_feature = _resolve_feature_name(root, settings)
    planned = plan_generation_files(
        GenerationPlanContext(
            settings=settings,
            clean_tree=tree,
            tokens=tokens,
            resolved_feature=resolved_feature,
            node_id=node_id,
            cluster_summary=cluster_summary,
            generation=generation,
            figma_root=root,
            package_name=package_name,
        )
    )
    return planned, tree
