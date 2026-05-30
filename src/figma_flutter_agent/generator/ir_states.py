"""Screen IR states and adaptive rules (Figma variant → emit-time behavior)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir_tree import index_clean_tree
from figma_flutter_agent.generator.variant_props import (
    get_variant_property,
    variant_input_has_error,
    variant_is_checked,
    variant_is_disabled,
    variant_is_loading,
)
from figma_flutter_agent.schemas import (
    AdaptiveRule,
    CleanDesignTreeNode,
    ComponentVariant,
    NodeType,
    ScreenIr,
    WidgetIrNode,
    WidgetIrOverrides,
    WidgetIrState,
)

_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
    }
)

_STATE_VARIANT_LABEL: dict[WidgetIrState, str] = {
    WidgetIrState.DISABLED: "Disabled",
    WidgetIrState.LOADING: "Loading",
    WidgetIrState.ERROR: "Error",
    WidgetIrState.SELECTED: "Selected",
}


def infer_widget_state(clean: CleanDesignTreeNode) -> WidgetIrState:
    """Map Figma component variant metadata to a canonical IR state."""
    if variant_is_loading(clean):
        return WidgetIrState.LOADING
    if variant_is_disabled(clean):
        return WidgetIrState.DISABLED
    if variant_input_has_error(clean):
        return WidgetIrState.ERROR
    if variant_is_checked(clean):
        return WidgetIrState.SELECTED
    return WidgetIrState.DEFAULT


def derive_state_by_figma_id(root: CleanDesignTreeNode) -> dict[str, WidgetIrState]:
    """Collect inferred states for interactive nodes under ``root``."""
    states: dict[str, WidgetIrState] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type in _INTERACTIVE_TYPES or node.variant is not None:
            state = infer_widget_state(node)
            if state != WidgetIrState.DEFAULT or node.variant is not None:
                states[node.id] = state
        for child in node.children:
            walk(child)

    walk(root)
    return states


def _find_ir_node(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if root.figma_id == figma_id:
        return root
    for child in root.children:
        found = _find_ir_node(child, figma_id)
        if found is not None:
            return found
    return None


def _merge_overrides(
    existing: WidgetIrOverrides | None,
    patch: WidgetIrOverrides | None,
) -> WidgetIrOverrides | None:
    if patch is None:
        return existing
    if existing is None:
        return patch
    return existing.model_copy(
        update=patch.model_dump(exclude_none=True),
    )


def _rule_matches(
    rule: AdaptiveRule,
    *,
    clean: CleanDesignTreeNode,
    effective_state: WidgetIrState,
    viewport_width: float | None,
) -> bool:
    when = rule.when
    if when.state is not None and when.state != effective_state:
        return False
    if when.min_viewport_width is not None:
        if viewport_width is None or viewport_width < when.min_viewport_width:
            return False
    if when.max_viewport_width is not None:
        if viewport_width is None or viewport_width > when.max_viewport_width:
            return False
    if when.variant_property is not None:
        actual = get_variant_property(clean, when.variant_property)
        expected = (when.variant_value or "").strip()
        if not expected or actual is None:
            return False
        if actual.strip().lower() != expected.lower():
            return False
    return True


def sync_state_to_clean_variant(
    clean: CleanDesignTreeNode,
    state: WidgetIrState,
) -> None:
    """Write canonical variant State onto the clean-tree node (in-place)."""
    if state == WidgetIrState.DEFAULT:
        return
    label = _STATE_VARIANT_LABEL.get(state)
    if label is None:
        return
    variant = clean.variant or ComponentVariant()
    props = dict(variant.variant_properties)
    props["State"] = label
    clean.variant = variant.model_copy(
        update={"state": label, "variant_properties": props},
    )


def apply_adaptive_rules_to_ir(
    screen_ir: ScreenIr,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
    viewport_width: float | None,
) -> None:
    """Merge matching ``adaptiveRules`` into IR nodes (in-place)."""
    for rule in screen_ir.adaptive_rules:
        clean = tree_by_id.get(rule.figma_id)
        ir_node = _find_ir_node(screen_ir.root, rule.figma_id)
        if clean is None or ir_node is None:
            continue
        explicit = screen_ir.state_by_figma_id.get(rule.figma_id)
        effective = explicit if explicit is not None else infer_widget_state(clean)
        if not _rule_matches(
            rule,
            clean=clean,
            effective_state=effective,
            viewport_width=viewport_width,
        ):
            continue
        if rule.overrides is not None:
            ir_node.overrides = _merge_overrides(ir_node.overrides, rule.overrides)
        if rule.wrap is not None:
            ir_node.wrap = rule.wrap


def enrich_screen_ir_states(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
) -> None:
    """Fill ``stateByFigmaId`` from the clean tree when the LLM omitted entries."""
    derived = derive_state_by_figma_id(root)
    for figma_id, state in derived.items():
        screen_ir.state_by_figma_id.setdefault(figma_id, state)


def apply_screen_ir_states_and_rules(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
    *,
    viewport_width: float | None = None,
) -> None:
    """Derive states, apply adaptive rules, and sync variant metadata on the clean tree."""
    tree_by_id = index_clean_tree(root)
    enrich_screen_ir_states(screen_ir, root)
    apply_adaptive_rules_to_ir(
        screen_ir,
        tree_by_id=tree_by_id,
        viewport_width=viewport_width,
    )
    for figma_id, state in screen_ir.state_by_figma_id.items():
        clean = tree_by_id.get(figma_id)
        if clean is None:
            continue
        sync_state_to_clean_variant(clean, state)


