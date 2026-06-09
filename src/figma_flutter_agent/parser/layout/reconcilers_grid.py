"""Grid-level layout reconcilers for clean design tree nodes."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
)

_PRODUCT_GRID_MIN_CARDS = 2


def _grid_child_visual_left(node: CleanDesignTreeNode) -> float:
    """Return the paint-space left edge for ordering GRID children left-to-right."""
    frame = node.geometry_frame
    if frame is not None:
        if frame.world_aabb is not None and frame.world_aabb.x is not None:
            return float(frame.world_aabb.x)
        if frame.parsed_world_aabb is not None and frame.parsed_world_aabb.x is not None:
            return float(frame.parsed_world_aabb.x)
    if node.children:
        return _grid_child_visual_left(node.children[0])
    return 0.0


def reconcile_grid_child_visual_order_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Sort GRID children by world left edge so emit matches Figma paint order."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.GRID or len(node.children) < 2:
            return node
        ordered = sorted(
            node.children,
            key=lambda child: (_grid_child_visual_left(child), child.id),
        )
        if [child.id for child in ordered] == [child.id for child in node.children]:
            return node
        return node.model_copy(update={"children": ordered})

    return walk(root)


def _grid_is_product_recommendation_grid(node: CleanDesignTreeNode) -> bool:
    """Two-up product tile grids (CARD children with edge-to-edge hero imagery)."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_has_edge_to_edge_hero_stack,
    )

    if node.type != NodeType.GRID or len(node.children) < _PRODUCT_GRID_MIN_CARDS:
        return False
    columns = node.grid_column_count
    if columns is not None and columns < 2:
        return False
    cards = [child for child in node.children if child.type == NodeType.CARD]
    if len(cards) < _PRODUCT_GRID_MIN_CARDS:
        return False
    hero_cards = sum(1 for card in cards if card_has_edge_to_edge_hero_stack(card))
    return hero_cards >= _PRODUCT_GRID_MIN_CARDS


def _grid_product_tile_fidelity_score(node: CleanDesignTreeNode) -> int:
    """Prefer grids whose cards still carry inline hero/metadata subtrees."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_is_product_tile_metadata,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_has_edge_to_edge_hero_stack,
    )
    from figma_flutter_agent.parser.interaction.enrichment import find_raster_photo_leaf

    score = 0
    for child in node.children:
        if child.type != NodeType.CARD or not card_has_edge_to_edge_hero_stack(child):
            continue
        hero = child.children[0]
        meta = child.children[1] if len(child.children) > 1 else None
        if find_raster_photo_leaf(hero) is not None or hero.image_asset_key:
            score += 100
        elif hero.children:
            score += 60
        elif hero.cluster_id:
            score += 5
        if meta is not None:
            if column_is_product_tile_metadata(meta, child):
                score += 100
            elif meta.children:
                score += 60
            elif meta.cluster_id:
                score += 5
    return score


def _product_grids_are_structural_duplicates(
    left: CleanDesignTreeNode,
    right: CleanDesignTreeNode,
) -> bool:
    """True when two grids are the same Figma duplicate product-card row."""
    if not _grid_is_product_recommendation_grid(left):
        return False
    if not _grid_is_product_recommendation_grid(right):
        return False
    if left.grid_column_count != right.grid_column_count:
        return False
    if len(left.children) != len(right.children):
        return False
    if left.grid_row_gap != right.grid_row_gap:
        return False
    if left.grid_column_gap != right.grid_column_gap:
        return False
    return True


def _product_card_has_inline_tile_content(card: CleanDesignTreeNode) -> bool:
    """True when a product card still carries renderable hero/metadata subtrees."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_is_product_tile_metadata,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_has_edge_to_edge_hero_stack,
    )
    from figma_flutter_agent.parser.interaction.enrichment import find_raster_photo_leaf

    if not card_has_edge_to_edge_hero_stack(card):
        return False
    hero = card.children[0]
    meta = card.children[1]
    photo = find_raster_photo_leaf(hero)
    hero_renderable = (
        (photo is not None and bool(photo.image_asset_key))
        or bool(hero.image_asset_key)
        or bool(hero.children)
    )
    if not hero_renderable:
        return False
    if column_is_product_tile_metadata(meta, card):
        return True
    return bool(meta.children) and meta.cluster_id is None


def _clear_cluster_ids_subtree(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Strip cluster references so hydrated tiles emit inline instead of widget stubs."""
    children = [_clear_cluster_ids_subtree(child) for child in node.children]
    return node.model_copy(update={"cluster_id": None, "children": children})


def _subtree_paths(node: CleanDesignTreeNode) -> dict[tuple[int, ...], str]:
    """Map structural child-index paths to node ids for a subtree root."""
    paths: dict[tuple[int, ...], str] = {}

    def walk(current: CleanDesignTreeNode, path: tuple[int, ...]) -> None:
        paths[path] = current.id
        for index, child in enumerate(current.children):
            walk(child, path + (index,))

    walk(node, ())
    return paths


def _collect_flatten_figma_id_pool(node: CleanDesignTreeNode) -> list[str]:
    """Collect pruned-instance node ids preserved on cluster stubs."""
    pool: list[str] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.flatten_figma_node_ids:
            pool.extend(current.flatten_figma_node_ids)
        stack.extend(reversed(current.children))
    return pool


def _allocate_hydration_figma_ids(
    target_card: CleanDesignTreeNode,
    *,
    count: int,
    reserved: set[str],
) -> list[str]:
    """Allocate fresh Figma-style ids when a pruned card lacks enough preserved ids."""
    if count <= 0:
        return []
    card_id = target_card.id
    if ":" in card_id:
        prefix, card_suffix = card_id.split(":", 1)
        max_suffix = int(card_suffix) if card_suffix.isdigit() else 0
    else:
        prefix = card_id
        max_suffix = 0

    def bump(candidate: str) -> None:
        nonlocal max_suffix
        if ":" not in candidate:
            return
        pre, suffix = candidate.split(":", 1)
        if pre != prefix or not suffix.isdigit():
            return
        max_suffix = max(max_suffix, int(suffix))

    for node_id in _subtree_paths(target_card).values():
        bump(node_id)
    for node_id in _collect_flatten_figma_id_pool(target_card):
        bump(node_id)
    for node_id in reserved:
        bump(node_id)

    allocated: list[str] = []
    for _ in range(count):
        while True:
            max_suffix += 1
            candidate = f"{prefix}:{max_suffix}"
            if candidate not in reserved:
                reserved.add(candidate)
                allocated.append(candidate)
                break
    return allocated


def _build_product_card_hydration_id_map(
    template: CleanDesignTreeNode,
    target: CleanDesignTreeNode,
    *,
    reserved_ids: set[str] | None = None,
) -> dict[str, str]:
    """Map template descendant ids onto the duplicate card's instance-local ids."""
    template_paths = _subtree_paths(template)
    target_paths = _subtree_paths(target)
    id_map: dict[str, str] = {template.id: target.id}
    used_target_ids = {target.id, *(reserved_ids or set())}
    template_only_ids: list[str] = []

    for path, template_id in sorted(template_paths.items()):
        if path == ():
            continue
        target_id = target_paths.get(path)
        if target_id is not None and target_id not in used_target_ids:
            id_map[template_id] = target_id
            used_target_ids.add(target_id)
            continue
        template_only_ids.append(template_id)

    spare_pool: list[str] = []
    for target_id in target_paths.values():
        if target_id not in used_target_ids:
            spare_pool.append(target_id)
    for flatten_id in _collect_flatten_figma_id_pool(target):
        if flatten_id not in used_target_ids and flatten_id not in spare_pool:
            spare_pool.append(flatten_id)

    for template_id in template_only_ids:
        target_id: str | None = None
        while spare_pool:
            candidate = spare_pool.pop(0)
            if candidate not in used_target_ids:
                target_id = candidate
                break
        if target_id is None:
            target_id = _allocate_hydration_figma_ids(
                target,
                count=1,
                reserved=used_target_ids,
            )[0]
        id_map[template_id] = target_id
        used_target_ids.add(target_id)

    return id_map


def _remap_subtree_node_ids(
    node: CleanDesignTreeNode,
    id_map: dict[str, str],
) -> CleanDesignTreeNode:
    """Rewrite ids in a copied subtree according to a hydration id map."""
    new_id = id_map.get(node.id, node.id)
    flatten = node.flatten_figma_node_ids
    if flatten:
        flatten = [id_map.get(item, item) for item in flatten]
    children = [_remap_subtree_node_ids(child, id_map) for child in node.children]
    return node.model_copy(
        update={
            "id": new_id,
            "children": children,
            "flatten_figma_node_ids": flatten,
        }
    )


def _hydrate_product_card_slot_from_template(
    target_slot: CleanDesignTreeNode,
    template_slot: CleanDesignTreeNode,
    *,
    reserved_ids: set[str],
) -> CleanDesignTreeNode | None:
    """Copy one hero or metadata slot from a template onto a pruned duplicate slot."""
    from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree

    id_map = _build_product_card_hydration_id_map(
        template_slot,
        target_slot,
        reserved_ids=reserved_ids,
    )
    template_paths = _subtree_paths(template_slot)
    if any(template_paths[path] not in id_map for path in template_paths):
        return None
    hydrated = _clear_cluster_ids_subtree(deep_copy_clean_tree(template_slot))
    reserved_ids.update(id_map.values())
    return _remap_subtree_node_ids(hydrated, id_map)


def _hydrate_product_card_from_template(
    card: CleanDesignTreeNode,
    template: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Copy inline hero/metadata from a rich template onto a pruned duplicate card."""
    if card.type != NodeType.CARD or template.type != NodeType.CARD:
        return card
    if len(card.children) < 2 or len(template.children) < 2:
        return card
    if _product_card_has_inline_tile_content(card):
        return card
    if not _product_card_has_inline_tile_content(template):
        return card
    reserved_ids: set[str] = {card.id, *(child.id for child in card.children)}
    hydrated_hero = _hydrate_product_card_slot_from_template(
        card.children[0],
        template.children[0],
        reserved_ids=reserved_ids,
    )
    hydrated_meta = _hydrate_product_card_slot_from_template(
        card.children[1],
        template.children[1],
        reserved_ids=reserved_ids,
    )
    if hydrated_hero is None or hydrated_meta is None:
        return card
    return card.model_copy(
        update={
            "name": card.name,
            "sizing": card.sizing,
            "geometry_frame": card.geometry_frame,
            "layout_slot": card.layout_slot,
            "layout_positioning": card.layout_positioning,
            "stack_placement": card.stack_placement,
            "children": [hydrated_hero, hydrated_meta],
        }
    )


def _product_card_match_keys(card: CleanDesignTreeNode) -> list[str]:
    """Return ordered lookup keys for matching a pruned card to a template tile."""
    keys: list[str] = []
    seen: set[str] = set()

    def add(key: str) -> None:
        if key and key not in seen:
            seen.add(key)
            keys.append(key)

    add(_product_card_match_key(card))
    if len(card.children) > 1 and card.children[1].cluster_id:
        add(f"cluster:{card.children[1].cluster_id}")
    if card.children and card.children[0].cluster_id:
        add(f"cluster:{card.children[0].cluster_id}")
    return keys


def _build_product_card_template_lookup(
    template_cards: list[CleanDesignTreeNode],
) -> dict[str, CleanDesignTreeNode]:
    """Index template tiles by every stable identity key they expose."""
    lookup: dict[str, CleanDesignTreeNode] = {}
    for item in template_cards:
        for key in _product_card_match_keys(item):
            lookup.setdefault(key, item)
    return lookup


def _build_pruned_cluster_alias_lookup(
    template_cards: list[CleanDesignTreeNode],
    pruned_cards: list[CleanDesignTreeNode],
) -> dict[str, CleanDesignTreeNode]:
    """Map meta-side component cluster ids from pruned tiles onto inline templates."""
    category_to_template = {
        key: item
        for item in template_cards
        if (key := _product_card_match_key(item))
    }
    aliases: dict[str, CleanDesignTreeNode] = {}
    for card in pruned_cards:
        if card.type != NodeType.CARD:
            continue
        category_key = _product_card_match_key(card)
        if not category_key:
            continue
        template = category_to_template.get(category_key)
        if template is None:
            continue
        if len(card.children) > 1 and card.children[1].cluster_id:
            aliases.setdefault(f"cluster:{card.children[1].cluster_id}", template)
        if card.children and card.children[0].cluster_id:
            aliases.setdefault(f"cluster:{card.children[0].cluster_id}", template)
    return aliases


def _resolve_product_card_template(
    card: CleanDesignTreeNode,
    *,
    template_by_key: dict[str, CleanDesignTreeNode],
    template_cards: list[CleanDesignTreeNode],
    index: int,
) -> CleanDesignTreeNode | None:
    """Pick the richest inline template for a cluster-pruned duplicate card."""
    for key in _product_card_match_keys(card):
        template = template_by_key.get(key)
        if template is not None:
            return template
    if index < len(template_cards):
        return template_cards[index]
    return None


def _hydrate_grid_cards_from_templates(
    grid: CleanDesignTreeNode,
    templates: list[CleanDesignTreeNode],
    *,
    template_by_key: dict[str, CleanDesignTreeNode] | None = None,
) -> list[CleanDesignTreeNode]:
    """Replace cluster-pruned cards with inline copies from the richest grid row."""
    template_cards = [item for item in templates if item.type == NodeType.CARD]
    if template_by_key is None:
        template_by_key = _build_product_card_template_lookup(template_cards)
    hydrated: list[CleanDesignTreeNode] = []
    for index, card in enumerate(grid.children):
        if card.type != NodeType.CARD:
            hydrated.append(card)
            continue
        if _product_card_has_inline_tile_content(card):
            hydrated.append(card)
            continue
        template = _resolve_product_card_template(
            card,
            template_by_key=template_by_key,
            template_cards=template_cards,
            index=index,
        )
        if template is None:
            hydrated.append(card)
            continue
        hydrated.append(_hydrate_product_card_from_template(card, template))
    return hydrated


def _product_card_catalog_category(card: CleanDesignTreeNode) -> str:
    """Uppercase category rail label (e.g. ``КУЛИНАРИЯ``, ``ЗАВТРАКИ``)."""
    from figma_flutter_agent.parser.interaction import _descendant_nodes

    if len(card.children) < 2:
        return ""
    for item in _descendant_nodes(card.children[1], 6):
        if item.type != NodeType.TEXT:
            continue
        text = (item.text or "").strip()
        if text and text == text.upper() and len(text) <= 32:
            return text
    return ""


def _product_card_match_key(card: CleanDesignTreeNode) -> str:
    """Stable identity for matching cloned product tiles across duplicate grids."""
    from figma_flutter_agent.parser.interaction import _descendant_nodes
    from figma_flutter_agent.parser.interaction.enrichment import find_raster_photo_leaf

    category = _product_card_catalog_category(card)
    if category:
        return f"cat:{category}"
    asset_key = ""
    if card.children:
        hero = card.children[0]
        photo = find_raster_photo_leaf(hero)
        asset_key = (photo.image_asset_key if photo else hero.image_asset_key) or ""
    if asset_key:
        return f"asset:{asset_key}"
    if len(card.children) > 1:
        for item in _descendant_nodes(card.children[1], 5):
            if item.type != NodeType.TEXT:
                continue
            text = (item.text or "").strip()
            if text:
                return f"title:{text[:48]}"
    return ""


def _product_card_content_fingerprint(card: CleanDesignTreeNode) -> tuple[str, str]:
    """Legacy fingerprint tuple retained for tests and diagnostics."""
    key = _product_card_match_key(card)
    if key.startswith("cat:"):
        return key.removeprefix("cat:"), ""
    if key.startswith("asset:"):
        return key.removeprefix("asset:"), ""
    if key.startswith("title:"):
        return "", key.removeprefix("title:")
    return "", ""


def reconcile_duplicate_product_card_grids_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Keep stacked duplicate product-card GRID rows and hydrate pruned card copies."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.COLUMN:
            return node

        patched_children: list[CleanDesignTreeNode] = []
        index = 0
        while index < len(node.children):
            child = node.children[index]
            if not _grid_is_product_recommendation_grid(child):
                patched_children.append(child)
                index += 1
                continue

            duplicate_run = [child]
            cursor = index + 1
            while cursor < len(node.children):
                candidate = node.children[cursor]
                if _product_grids_are_structural_duplicates(duplicate_run[0], candidate):
                    duplicate_run.append(candidate)
                    cursor += 1
                else:
                    break

            if len(duplicate_run) == 1:
                patched_children.append(child)
            else:
                best = max(duplicate_run, key=_grid_product_tile_fidelity_score)
                template_cards = [
                    item for item in best.children if item.type == NodeType.CARD
                ]
                pruned_cards = [
                    card
                    for grid in duplicate_run
                    for card in grid.children
                    if card.type == NodeType.CARD
                    and not _product_card_has_inline_tile_content(card)
                ]
                template_by_key = _build_product_card_template_lookup(template_cards)
                template_by_key.update(
                    _build_pruned_cluster_alias_lookup(template_cards, pruned_cards)
                )
                for grid in duplicate_run:
                    hydrated_children = _hydrate_grid_cards_from_templates(
                        grid,
                        template_cards,
                        template_by_key=template_by_key,
                    )
                    patched_children.append(
                        grid.model_copy(update={"children": hydrated_children})
                    )
            index = cursor

        return node.model_copy(update={"children": patched_children})

    return walk(root)
