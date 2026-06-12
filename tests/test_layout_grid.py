"""Tests for Figma GRID auto-layout mapped to GridView.count."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.layout import (
    extract_grid_column_count,
    extract_grid_gaps,
    infer_container_type,
)
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    Alignment,
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    SizingMode,
)


def test_infer_container_type_maps_grid_layout_mode() -> None:
    node = {"layoutMode": "GRID", "gridColumnCount": 3}

    assert infer_container_type(node) == NodeType.GRID


def test_extract_grid_metrics() -> None:
    node = {
        "gridColumnCount": 3,
        "gridRowGap": 10,
        "gridColumnGap": 14,
        "itemSpacing": 4,
    }

    assert extract_grid_column_count(node, child_count=6) == 3
    assert extract_grid_gaps(node) == (10.0, 14.0)


def test_grid_frame_renders_grid_view_count() -> None:
    root = json.loads(Path("tests/fixtures/figma_grid_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    assert tree.type == NodeType.GRID
    assert tree.grid_column_count == 2
    assert tree.grid_row_gap == 12.0
    assert tree.grid_column_gap == 16.0

    layout = render_layout_file(tree, feature_name="products", uses_svg=False)[
        "lib/generated/products_layout.dart"
    ]

    assert "GridView.count(" in layout
    assert "final crossAxisCount" in layout
    assert "LayoutBuilder(" in layout
    assert "AppBreakpoints.isMobileLarge(width)" in layout
    assert "AppBreakpoints.isDesktop(width)" in layout
    assert "mainAxisSpacing: 12.0" in layout
    assert "crossAxisSpacing: 16.0" in layout
    assert "padding: const EdgeInsets.all(8.0)" in layout or "fromLTRB(8.0" in layout
    assert "Text('A'" in layout
    assert "Text('D'" in layout


def test_embedded_chunk_grid_root_uses_shrink_wrap() -> None:
    from figma_flutter_agent.generator.layout.widgets import render_node_body

    grid = CleanDesignTreeNode(
        id="grid",
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        grid_row_gap=16.0,
        grid_column_gap=16.0,
        sizing=Sizing(width=357.0, height=314.0),
        children=[
            CleanDesignTreeNode(id="a", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="b", name="B", type=NodeType.TEXT, text="B"),
        ],
    )
    body = render_node_body(grid, uses_svg=False, is_layout_root=False, parent_type=None)
    assert "GridView.count(shrinkWrap: true" in body
    assert "NeverScrollableScrollPhysics()" in body


def test_nested_grid_in_column_uses_shrink_wrap() -> None:
    grid_child = CleanDesignTreeNode(
        id="2",
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        grid_row_gap=8,
        grid_column_gap=8,
        children=[
            CleanDesignTreeNode(id="3", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="4", name="B", type=NodeType.TEXT, text="B"),
        ],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[grid_child],
    )

    layout = render_layout_file(parent, feature_name="nested_grid", uses_svg=False)[
        "lib/generated/nested_grid_layout.dart"
    ]

    assert "shrinkWrap: true" in layout
    assert "NeverScrollableScrollPhysics()" in layout
    assert "ClampingScrollPhysics()" not in layout
    assert "GridView.count(" in layout


def test_fill_height_grid_in_column_uses_expanded() -> None:
    grid_child = CleanDesignTreeNode(
        id="2",
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        sizing=Sizing(height_mode=SizingMode.FILL),
        children=[CleanDesignTreeNode(id="3", name="A", type=NodeType.TEXT, text="A")],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[grid_child],
    )

    layout = render_layout_file(parent, feature_name="grid_fill", uses_svg=False)[
        "lib/generated/grid_fill_layout.dart"
    ]

    assert "Expanded(child: RepaintBoundary(child: GridView.count(" in layout


def test_grid_child_aspect_ratio_from_sized_children() -> None:
    card = CleanDesignTreeNode(
        id="610:538",
        name="Card",
        type=NodeType.CARD,
        sizing=Sizing(width=170.5, height=310.5),
        children=[CleanDesignTreeNode(id="610:539", name="Title", type=NodeType.TEXT, text="X")],
    )
    grid = CleanDesignTreeNode(
        id="610:537",
        name="Grid",
        type=NodeType.GRID,
        sizing=Sizing(width=357.0, height=314.0),
        grid_column_count=2,
        grid_row_gap=8.0,
        grid_column_gap=16.0,
        children=[card, card.model_copy(deep=True)],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[grid],
    )

    layout = render_layout_file(parent, feature_name="product_cards", uses_svg=False)[
        "lib/generated/product_cards_layout.dart"
    ]

    assert "childAspectRatio: 0.55" in layout


def _product_card(hero_id: str, *, rich: bool) -> CleanDesignTreeNode:
    hero_children = (
        [
            CleanDesignTreeNode(
                id=f"{hero_id}:img",
                name="Photo",
                type=NodeType.IMAGE,
                image_asset_key=f"assets/images/{hero_id}.png",
            )
        ]
        if rich
        else []
    )
    hero = CleanDesignTreeNode(
        id=hero_id,
        name="Hero",
        type=NodeType.STACK,
        cluster_id=None if rich else "cluster_hero",
        sizing=Sizing(width=170.5, height=171.0),
        children=hero_children,
    )
    meta_children = (
        [
            CleanDesignTreeNode(
                id=f"{hero_id}:title",
                name="Title",
                type=NodeType.TEXT,
                text="Title",
            )
        ]
        if rich
        else [
            CleanDesignTreeNode(
                id=f"{hero_id}:stub",
                name="Stub",
                type=NodeType.COLUMN,
                cluster_id="cluster_stub",
                children=[],
            )
        ]
    )
    meta = CleanDesignTreeNode(
        id=f"{hero_id}:meta",
        name="Meta",
        type=NodeType.COLUMN,
        cluster_id=None if rich else "cluster_meta",
        sizing=Sizing(width=170.5, height=143.5),
        alignment=Alignment(main="spaceBetween", cross="stretch"),
        children=meta_children,
    )
    return CleanDesignTreeNode(
        id=f"{hero_id}:card",
        name="Card",
        type=NodeType.CARD,
        sizing=Sizing(width=170.5, height=314.5),
        children=[hero, meta],
    )


def _product_grid(grid_id: str, *, rich: bool) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=grid_id,
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        grid_row_gap=16.0,
        grid_column_gap=16.0,
        sizing=Sizing(width=357.0, height=314.0),
        children=[
            _product_card(f"{grid_id}a", rich=rich),
            _product_card(f"{grid_id}b", rich=rich),
        ],
    )


def test_reconcile_duplicate_product_card_grids_keeps_three_hydrated_rows() -> None:
    from figma_flutter_agent.parser.interaction.enrichment import find_raster_photo_leaf
    from figma_flutter_agent.parser.layout import (
        reconcile_duplicate_product_card_grids_in_tree,
    )

    column = CleanDesignTreeNode(
        id="col",
        name="Column",
        type=NodeType.COLUMN,
        children=[
            _product_grid("rich", rich=True),
            _product_grid("empty", rich=False),
            _product_grid("empty2", rich=False),
        ],
    )
    reconciled = reconcile_duplicate_product_card_grids_in_tree(column)
    grids = [child for child in reconciled.children if child.type == NodeType.GRID]
    assert len(grids) == 3
    assert [grid.id for grid in grids] == ["rich", "empty", "empty2"]
    for grid in grids:
        for card in grid.children:
            hero = card.children[0]
            assert find_raster_photo_leaf(hero) is not None


def test_reconcile_grid_child_visual_order_swaps_reversed_siblings() -> None:
    from figma_flutter_agent.parser.layout import reconcile_grid_child_visual_order_in_tree
    from figma_flutter_agent.schemas.geometry import GeometryFrame, GeomRect

    left = CleanDesignTreeNode(
        id="left",
        name="Left",
        type=NodeType.CARD,
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=10.0, y=0.0, width=100.0, height=100.0),
        ),
    )
    right = CleanDesignTreeNode(
        id="right",
        name="Right",
        type=NodeType.CARD,
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=140.0, y=0.0, width=100.0, height=100.0),
        ),
    )
    grid = CleanDesignTreeNode(
        id="grid",
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        children=[right, left],
    )
    reconciled = reconcile_grid_child_visual_order_in_tree(grid)
    assert [child.id for child in reconciled.children] == ["left", "right"]


def test_reconcile_product_hero_photo_viewport_snaps_raster_leaf() -> None:
    from figma_flutter_agent.parser.layout.reconcilers_media import (
        reconcile_product_hero_photo_viewport_in_tree,
    )
    from figma_flutter_agent.schemas.geometry import StackPlacement
    from figma_flutter_agent.schemas.style import NodeStyle

    photo = CleanDesignTreeNode(
        id="photo",
        name="photo",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=171.0, height=171.0),
        image_asset_key="assets/images/hero.png",
        stack_placement=StackPlacement(
            horizontal="LEFT_RIGHT",
            vertical="TOP_BOTTOM",
            top=0.3,
            right=-0.5,
        ),
    )
    hero = CleanDesignTreeNode(
        id="hero",
        name="hero",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FILL,
            width=170.5,
            height_mode=SizingMode.FIXED,
            height=171.0,
        ),
        children=[photo],
    )
    meta = CleanDesignTreeNode(
        id="meta",
        name="meta",
        type=NodeType.COLUMN,
        sizing=Sizing(height=120.0),
        children=[
            CleanDesignTreeNode(
                id="title",
                name="title",
                type=NodeType.TEXT,
                text="BREAKFAST",
            ),
        ],
    )
    card = CleanDesignTreeNode(
        id="card",
        name="card",
        type=NodeType.CARD,
        sizing=Sizing(width=170.5, height=291.0),
        style=NodeStyle(background_color="0xFFFFFFFF"),
        children=[hero, meta],
    )
    reconciled = reconcile_product_hero_photo_viewport_in_tree(card)
    snapped = reconciled.children[0].children[0]
    assert snapped.sizing.width == 170.5
    assert snapped.sizing.height == 171.0
    assert snapped.stack_placement is not None
    assert snapped.stack_placement.top == 0.0


def test_cart_recommended_section_emits_three_product_grid_rows() -> None:
    import json
    from pathlib import Path

    from figma_flutter_agent.generator.normalize import normalize_clean_tree
    from figma_flutter_agent.parser.tree import build_clean_tree

    cart_path = Path(r"E:/@dev/flutter-demo-project/ataev/.debug/raw/cart_layout.json")
    if not cart_path.is_file():
        import pytest

        pytest.skip("offline cart fixture unavailable")
    raw = json.loads(cart_path.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(raw)
    root = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=Path(r"E:/@dev/flutter-demo-project/ataev"),
    )

    def find_grids(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
        found: list[CleanDesignTreeNode] = []
        if node.type == NodeType.GRID:
            cards = [child for child in node.children if child.type == NodeType.CARD]
            if len(cards) >= 2:
                found.append(node)
        for child in node.children:
            found.extend(find_grids(child))
        return found

    product_grids = find_grids(root)
    assert len(product_grids) == 3
    assert all(len(grid.children) == 2 for grid in product_grids)

    from figma_flutter_agent.generator.ir.tree import validate_unique_node_ids
    from figma_flutter_agent.parser.interaction.enrichment import find_raster_photo_leaf

    validate_unique_node_ids(root)

    def card_asset(card: CleanDesignTreeNode) -> str:
        hero = card.children[0]
        photo = find_raster_photo_leaf(hero)
        return (photo.image_asset_key if photo else "") or ""

    for grid_id in ("610:585", "610:633"):
        grid = next(grid for grid in product_grids if grid.id == grid_id)
        assert card_asset(grid.children[0]).endswith("image_610_558.png")
        assert card_asset(grid.children[1]).endswith("image_610_540.png")

    from figma_flutter_agent.generator.layout.widgets.emit import render_node_body

    pancake = next(
        card
        for grid in product_grids
        if grid.id == "610:537"
        for card in grid.children
        if card_asset(card).endswith("image_610_558.png")
    )
    pancake_emit = render_node_body(pancake, uses_svg=True, theme_variant="material_3")
    hero = pancake.children[0]
    photo = find_raster_photo_leaf(hero)
    assert photo is not None
    assert float(photo.sizing.width or 0) == float(hero.sizing.width or 0)
    assert float(photo.sizing.height or 0) == float(hero.sizing.height or 0)
    assert "image_610_558.png" in pancake_emit
    assert "BoxFit.cover" in pancake_emit
    assert "AspectRatio(aspectRatio:" in pancake_emit
    assert "Positioned(top: 10.0, left: 10.0, child: DecoratedBox" not in pancake_emit
    assert "SizedBox(height: 181.0" not in pancake_emit


def test_root_grid_responsive_disabled_skips_layout_builder() -> None:
    root = json.loads(Path("tests/fixtures/figma_grid_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    layout = render_layout_file(
        tree,
        feature_name="products",
        uses_svg=False,
        responsive_enabled=False,
    )["lib/generated/products_layout.dart"]

    assert "LayoutBuilder(" not in layout
    assert "crossAxisCount: 2" in layout
