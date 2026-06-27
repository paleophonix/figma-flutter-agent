"""Pre-validate sanitizers for LLM screen IR drift against the clean tree."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from figma_flutter_agent.config.models import SemanticsSettings
from figma_flutter_agent.generator.ir.presence.kinds import ir_kind_for_clean_node
from figma_flutter_agent.generator.ir.presence.tree import ir_node_by_figma_id
from figma_flutter_agent.generator.ir.tree import index_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr, WidgetIrKind, WidgetIrNode


@dataclass(frozen=True)
class SanitizeSummary:
    """Counts of LLM-drift fixes applied during ``sanitize_screen_ir_llm_drift``."""

    omit_ids_removed: int = 0
    state_keys_pruned: int = 0
    adaptive_rules_dropped: int = 0
    extracted_downgraded: int = 0
    extracted_children_stripped: int = 0
    phantom_nodes_pruned: int = 0
    duplicate_nodes_dropped: int = 0
    orphan_refs_removed: int = 0


def sanitize_screen_ir_omit_figma_ids(
    screen_ir: ScreenIr, clean_tree: CleanDesignTreeNode
) -> ScreenIr:
    """Remove real clean-tree node IDs (including root) from ``omit_figma_ids``."""
    if not screen_ir.omit_figma_ids:
        return screen_ir
    tree_by_id = index_clean_tree(clean_tree)
    before = list(screen_ir.omit_figma_ids)
    sanitized = [id_ for id_ in before if id_ not in tree_by_id]
    removed = len(before) - len(sanitized)
    if removed == 0:
        return screen_ir
    logger.info(
        "Sanitized screenIr omitFigmaIds: removed {} real clean-tree id(s)",
        removed,
    )
    return screen_ir.model_copy(update={"omit_figma_ids": sanitized})


def sanitize_screen_ir_state_by_figma_id(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
) -> int:
    """Drop ``stateByFigmaId`` entries that reference nodes outside the clean tree."""
    if not screen_ir.state_by_figma_id:
        return 0
    tree_by_id = index_clean_tree(clean_tree)
    pruned = 0
    for figma_id in list(screen_ir.state_by_figma_id):
        if figma_id not in tree_by_id:
            logger.warning(
                "Dropped screenIr stateByFigmaId for figmaId {}: not in clean tree",
                figma_id,
            )
            del screen_ir.state_by_figma_id[figma_id]
            pruned += 1
    if pruned:
        logger.info("Sanitized screenIr stateByFigmaId: pruned {} stale key(s)", pruned)
    return pruned


def sanitize_screen_ir_orphan_refs(screen_ir: ScreenIr) -> int:
    """Strip ``ref`` from IR nodes whose ``kind`` is not ``extracted``.

    LLM output sometimes attaches ``ref.widgetName`` to structural kinds (for example
    ``stack``). Emitters only honor refs on ``kind=extracted``; orphan refs mislead
    repair agents and structured-output validators without affecting emit.

    Returns:
        Count of refs removed.
    """
    removed = 0

    def walk(ir_node: WidgetIrNode) -> None:
        nonlocal removed
        if ir_node.kind != WidgetIrKind.EXTRACTED and ir_node.ref is not None:
            ref_name = (ir_node.ref.widget_name or "").strip()
            if ref_name:
                logger.warning(
                    "Stripped orphan screenIr ref {!r} at {} (kind={})",
                    ref_name,
                    ir_node.figma_id,
                    ir_node.kind.value,
                )
            ir_node.ref = None
            removed += 1
        for child in ir_node.children:
            walk(child)

    walk(screen_ir.root)
    if removed:
        logger.info("Sanitized screenIr orphan refs: removed {} ref(s)", removed)
    return removed


def sanitize_screen_ir_extracted_refs(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str],
    canonical_extracted_widget_names: frozenset[str] | None = None,
    widget_suffix: str = "Widget",
) -> tuple[int, int]:
    """Downgrade or normalize malformed ``kind=extracted`` IR nodes.

    Returns:
        Tuple of ``(downgraded_count, children_stripped_count)``.
    """
    from figma_flutter_agent.generator.subtree import collect_subtree_widget_specs

    tree_by_id = index_clean_tree(clean_tree)
    if canonical_extracted_widget_names is not None:
        allowed = set(canonical_extracted_widget_names)
    else:
        allowed = set(extracted_widget_names)
        for spec in collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix):
            allowed.add(spec.class_name)
    downgraded = 0
    children_stripped = 0

    def walk(ir_node: WidgetIrNode) -> None:
        nonlocal downgraded, children_stripped
        if ir_node.kind == WidgetIrKind.EXTRACTED:
            ref_name = (ir_node.ref.widget_name if ir_node.ref else "").strip()
            clean = tree_by_id.get(ir_node.figma_id)
            from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

            if clean is not None and must_inline_extracted_widget_host(clean):
                logger.warning(
                    "Downgraded screenIr extracted ref {!r} at {}: form/input hosts must inline",
                    ref_name,
                    ir_node.figma_id,
                )
                ir_node.kind = ir_kind_for_clean_node(clean)
                ir_node.ref = None
                downgraded += 1
            elif ref_name and ref_name in allowed:
                if ir_node.children:
                    stripped_count = len(ir_node.children)
                    logger.warning(
                        "Stripped {} child node(s) from screenIr extracted ref {!r} at {}",
                        stripped_count,
                        ref_name,
                        ir_node.figma_id,
                    )
                    ir_node.children = []
                    children_stripped += stripped_count
            else:
                if clean is None:
                    logger.warning(
                        "Dropped screenIr extracted ref {!r} at {}: figmaId absent from clean tree",
                        ref_name,
                        ir_node.figma_id,
                    )
                else:
                    logger.warning(
                        "Downgraded screenIr extracted ref {!r} at {}: not in extractedWidgets",
                        ref_name,
                        ir_node.figma_id,
                    )
                    ir_node.kind = ir_kind_for_clean_node(clean)
                    ir_node.ref = None
                    downgraded += 1
        for child in ir_node.children:
            walk(child)

    walk(screen_ir.root)
    if downgraded:
        logger.info(
            "Sanitized screenIr extracted refs: downgraded {} orphan node(s)",
            downgraded,
        )
    return downgraded, children_stripped


def sanitize_screen_ir_adaptive_rules(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
) -> ScreenIr:
    """Drop adaptive rules that target nodes outside the clean tree or screen IR graph."""
    if not screen_ir.adaptive_rules:
        return screen_ir
    tree_by_id = index_clean_tree(clean_tree)
    kept = []
    dropped = 0
    for rule in screen_ir.adaptive_rules:
        if rule.figma_id not in tree_by_id:
            logger.warning(
                "Dropped screenIr adaptiveRule for figmaId {}: not in clean tree",
                rule.figma_id,
            )
            dropped += 1
            continue
        if ir_node_by_figma_id(screen_ir.root, rule.figma_id) is None:
            logger.warning(
                "Dropped screenIr adaptiveRule for figmaId {}: not present in screenIr graph",
                rule.figma_id,
            )
            dropped += 1
            continue
        kept.append(rule)
    if dropped == 0:
        return screen_ir
    logger.info(
        "Sanitized screenIr adaptiveRules: kept {} of {}",
        len(kept),
        len(screen_ir.adaptive_rules),
    )
    return screen_ir.model_copy(update={"adaptive_rules": kept})


def sanitize_screen_ir_phantom_nodes(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
) -> int:
    """Prune IR subtrees whose ``figmaId`` is absent from the clean tree (root preserved)."""
    tree_by_id = index_clean_tree(clean_tree)
    root_id = screen_ir.root.figma_id
    pruned = 0

    def walk(ir_node: WidgetIrNode) -> list[WidgetIrNode]:
        nonlocal pruned
        kept: list[WidgetIrNode] = []
        for child in ir_node.children:
            if child.figma_id not in tree_by_id:
                logger.warning(
                    "Pruned phantom screenIr node {}: not in clean tree",
                    child.figma_id,
                )
                pruned += 1
                continue
            child.children = walk(child)
            kept.append(child)
        return kept

    screen_ir.root.children = walk(screen_ir.root)
    if pruned:
        logger.info("Sanitized screenIr phantom nodes: pruned {} node(s)", pruned)
    if root_id not in tree_by_id:
        return pruned
    return pruned


def sanitize_screen_ir_duplicate_figma_ids(screen_ir: ScreenIr) -> int:
    """Drop duplicate ``figmaId`` occurrences; first DFS preorder occurrence wins."""
    seen: set[str] = {screen_ir.root.figma_id}
    dropped = 0

    def walk(ir_node: WidgetIrNode) -> None:
        nonlocal dropped
        kept: list[WidgetIrNode] = []
        for child in ir_node.children:
            if child.figma_id in seen:
                logger.warning(
                    "Dropped duplicate screenIr node {} (second occurrence)",
                    child.figma_id,
                )
                dropped += 1
                continue
            seen.add(child.figma_id)
            kept.append(child)
            walk(child)
        ir_node.children = kept

    walk(screen_ir.root)
    if dropped:
        logger.info("Sanitized screenIr duplicate figmaIds: dropped {} node(s)", dropped)
    return dropped


def sanitize_screen_ir_llm_drift(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    declared_extracted_widget_names: frozenset[str],
    canonical_extracted_widget_names: frozenset[str] | None = None,
    widget_suffix: str = "Widget",
    strip_llm_semantic_kinds: bool = False,
    semantics: SemanticsSettings | None = None,
) -> SanitizeSummary:
    """Apply all LLM-drift sanitizers before strict IR validation."""
    omit_before = len(screen_ir.omit_figma_ids)
    rules_before = len(screen_ir.adaptive_rules)

    updated_ir = sanitize_screen_ir_omit_figma_ids(screen_ir, clean_tree)
    if updated_ir is not screen_ir:
        screen_ir.omit_figma_ids = updated_ir.omit_figma_ids

    state_pruned = sanitize_screen_ir_state_by_figma_id(screen_ir, clean_tree)

    updated_ir = sanitize_screen_ir_adaptive_rules(screen_ir, clean_tree)
    if updated_ir is not screen_ir:
        screen_ir.adaptive_rules = updated_ir.adaptive_rules

    downgraded, children_stripped = sanitize_screen_ir_extracted_refs(
        screen_ir,
        clean_tree,
        extracted_widget_names=declared_extracted_widget_names,
        canonical_extracted_widget_names=canonical_extracted_widget_names,
        widget_suffix=widget_suffix,
    )

    orphan_refs_removed = sanitize_screen_ir_orphan_refs(screen_ir)

    phantom_pruned = sanitize_screen_ir_phantom_nodes(screen_ir, clean_tree)
    duplicate_dropped = sanitize_screen_ir_duplicate_figma_ids(screen_ir)

    from figma_flutter_agent.generator.ir.presence.semantics import (
        sanitize_screen_ir_semantic_kinds,
        strip_screen_ir_classification_hints,
    )

    resolved_semantics = semantics or SemanticsSettings()
    if strip_llm_semantic_kinds:
        if resolved_semantics.authoritative_classifier:
            sanitize_screen_ir_semantic_kinds(
                screen_ir,
                grey_zone_min=resolved_semantics.grey_zone_min,
                llm_gray_zone_enabled=resolved_semantics.llm_gray_zone_annotations,
            )
        elif not resolved_semantics.llm_gray_zone_annotations:
            strip_screen_ir_classification_hints(screen_ir)

    return SanitizeSummary(
        omit_ids_removed=omit_before - len(screen_ir.omit_figma_ids),
        state_keys_pruned=state_pruned,
        adaptive_rules_dropped=rules_before - len(screen_ir.adaptive_rules),
        extracted_downgraded=downgraded,
        extracted_children_stripped=children_stripped,
        phantom_nodes_pruned=phantom_pruned,
        duplicate_nodes_dropped=duplicate_dropped,
        orphan_refs_removed=orphan_refs_removed,
    )
