"""Regression laws from niyama_order batch repair (generic, not screen-patched)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.layout.flex_policy.wrap import (
    repair_overflowbox_unbounded_row_flex_in_source,
)
from figma_flutter_agent.generator.layout.scroll import (
    _stack_supports_horizontal_item_scroll,
    horizontal_scroll_item_carrier,
)
from figma_flutter_agent.generator.layout.widgets.svg import (
    _layout_slot_raster_emit_dimensions,
    _render_exported_vector,
)
from figma_flutter_agent.parser.boundaries.assets import (
    discover_asset_path_for_node,
    lookup_asset_path_for_component_vector_family,
)
from figma_flutter_agent.parser.interaction.product import (
    _stack_hosts_horizontal_product_carrier_row,
    horizontal_scroll_product_tile,
    layout_fact_stack_component_catalog_product_tile,
    layout_fact_stack_detail_hero_banner_host,
)
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    StackPlacement,
)


def test_repair_overflowbox_pins_width_on_height_only_sizedbox_with_expanded() -> None:
  source = (
      "ClipRect(child: Align(alignment: Alignment.centerLeft, child: OverflowBox("
      "alignment: Alignment.centerLeft, maxWidth: 81.0, "
      "child: Row(children: [SizedBox(height: 28.0, child: Row(children: ["
      "Expanded(child: Text('Guests'))]))]))))"
  )
  repaired = repair_overflowbox_unbounded_row_flex_in_source(source)
  assert "SizedBox(height: 28.0, width: 81.0" in repaired


def test_render_exported_vector_routes_svg_image_asset_key_to_svg_picture() -> None:
  node = CleanDesignTreeNode(
      id="1:2",
      name="bg",
      type=NodeType.VECTOR,
      sizing=Sizing(width=375.0, height=812.0),
      style=NodeStyle(),
      image_asset_key="assets/illustrations/hero_1_2.svg",
  )
  dart = _render_exported_vector(node, uses_svg=True)
  assert dart is not None
  assert "SvgPicture.asset" in dart
  assert "Image.asset" not in dart


def test_layout_slot_raster_emit_dimensions_clamps_to_stack_slot() -> None:
  node = CleanDesignTreeNode(
      id="1:3",
      name="thumb",
      type=NodeType.IMAGE,
      sizing=Sizing(width=76.0, height=76.0),
      style=NodeStyle(render_bounds_expand=None),
      stack_placement=StackPlacement(left=0.0, top=0.0, width=76.0, height=76.0),
  )
  node.style.render_bounds_expand = Padding(left=22.0, right=22.0, top=29.0, bottom=29.0)
  width, height = _layout_slot_raster_emit_dimensions(node, 76.0, 76.0)
  assert width == 76.0
  assert height == 76.0


def test_horizontal_scroll_inferred_for_wide_multi_tile_row() -> None:
  tiles = [
      CleanDesignTreeNode(
          id=f"1:{index}",
          name=f"tile{index}",
          type=NodeType.CARD,
          sizing=Sizing(width=140.0, height=180.0),
          style=NodeStyle(),
      )
      for index in range(3)
  ]
  row = CleanDesignTreeNode(
      id="1:10",
      name="row",
      type=NodeType.ROW,
      sizing=Sizing(width=446.0, height=180.0),
      style=NodeStyle(),
      children=tiles,
  )
  stack = CleanDesignTreeNode(
      id="1:11",
      name="swipe",
      type=NodeType.STACK,
      sizing=Sizing(width=375.0, height=200.0),
      style=NodeStyle(),
      scroll_axis="none",
      children=[row],
  )
  assert _stack_supports_horizontal_item_scroll(stack)
  assert horizontal_scroll_item_carrier(stack) is row


def test_detail_hero_host_excludes_horizontal_product_carrier() -> None:
  tiles = [
      CleanDesignTreeNode(
          id=f"2:{index}",
          name=f"tile{index}",
          type=NodeType.CARD,
          sizing=Sizing(width=140.0, height=180.0),
          style=NodeStyle(),
      )
      for index in range(3)
  ]
  row = CleanDesignTreeNode(
      id="2:10",
      name="row",
      type=NodeType.ROW,
      sizing=Sizing(width=446.0, height=180.0),
      style=NodeStyle(),
      children=tiles,
  )
  stack = CleanDesignTreeNode(
      id="2:11",
      name="swipe",
      type=NodeType.STACK,
      sizing=Sizing(width=375.0, height=200.0),
      style=NodeStyle(),
      scroll_axis="none",
      children=[row],
  )
  assert _stack_hosts_horizontal_product_carrier_row(stack)
  assert not layout_fact_stack_detail_hero_banner_host(stack)


def test_orphan_raster_pairing_requires_positive_label_overlap(tmp_path: Path) -> None:
  images = tmp_path / "assets" / "images"
  images.mkdir(parents=True)
  (images / "portrait.png").write_bytes(b"png")
  (images / "sussi.png").write_bytes(b"png")

  def product_row(row_id: str, title: str, image_id: str) -> CleanDesignTreeNode:
      return CleanDesignTreeNode(
          id=row_id,
          name="Card",
          type=NodeType.ROW,
          children=[
              CleanDesignTreeNode(
                  id=image_id,
                  name="Img",
                  type=NodeType.IMAGE,
                  sizing=Sizing(width=76.0, height=76.0),
              ),
              CleanDesignTreeNode(
                  id=f"{row_id}:title",
                  name="Title",
                  type=NodeType.TEXT,
                  text=title,
              ),
          ],
      )

  root = CleanDesignTreeNode(
      id="1:root",
      name="Modal",
      type=NodeType.STACK,
      children=[
          product_row("1:row-a", "Окинава Монтерей", "1:img-a"),
          product_row("1:row-b", "Соевый Соус", "1:img-b"),
      ],
  )
  manifest = local_asset_manifest_from_project(tmp_path, clean_tree=root)
  bound = {entry.node_id: entry.asset_path for entry in manifest.entries if entry.kind == "image"}
  assert bound.get("1:img-a") != "assets/images/portrait.png"
  assert bound.get("1:img-b") != "assets/images/portrait.png"


def test_component_vector_family_uses_component_ref_prefix(tmp_path: Path) -> None:
  icons = tmp_path / "assets" / "icons"
  icons.mkdir(parents=True)
  (icons / "vector_1162_10106.svg").write_text("<svg></svg>", encoding="utf-8")
  asset_index = {"1162_10106": "assets/icons/vector_1162_10106.svg"}
  users_leaf = "I4408:44904;1162:10180;4181:43463"
  assert (
      lookup_asset_path_for_component_vector_family(
          asset_index,
          users_leaf,
          component_ref="4181:43464",
      )
      is None
  )
  assert discover_asset_path_for_node(
      tmp_path,
      users_leaf,
      asset_index=asset_index,
      component_ref="4181:43464",
  ) is None


def test_horizontal_scroll_inferred_for_component_product_small_stacks() -> None:
  tiles = [
      CleanDesignTreeNode(
          id=f"3:{index}",
          name="Product small",
          type=NodeType.STACK,
          sizing=Sizing(width=142.0, height=239.0),
          style=NodeStyle(),
          component_ref="1356:10701",
          variant=ComponentVariant(
              component_id="1356:10701",
              component_name="Product small",
              variant_properties={"Product": "Add"},
          ),
          children=[
              CleanDesignTreeNode(
                  id=f"3:{index}:title",
                  name="Title",
                  type=NodeType.TEXT,
                  text="Соусы",
              ),
              CleanDesignTreeNode(
                  id=f"3:{index}:img",
                  name="Img",
                  type=NodeType.IMAGE,
                  sizing=Sizing(width=142.0, height=137.0),
              ),
          ],
      )
      for index in range(3)
  ]
  row = CleanDesignTreeNode(
      id="3:10",
      name="product",
      type=NodeType.ROW,
      sizing=Sizing(width=446.0, height=239.0),
      style=NodeStyle(),
      children=tiles,
  )
  stack = CleanDesignTreeNode(
      id="3:11",
      name="Swipe",
      type=NodeType.STACK,
      sizing=Sizing(width=375.0, height=239.0),
      style=NodeStyle(),
      scroll_axis="none",
      children=[row],
  )
  assert layout_fact_stack_component_catalog_product_tile(tiles[0])
  assert _stack_supports_horizontal_item_scroll(stack)
  assert horizontal_scroll_item_carrier(stack) is row
  assert not layout_fact_stack_detail_hero_banner_host(stack)


def test_layout_slot_raster_emit_dimensions_clamps_expanded_bounds_to_sizing() -> None:
  node = CleanDesignTreeNode(
      id="1:4",
      name="thumb",
      type=NodeType.IMAGE,
      sizing=Sizing(width=76.0, height=76.0),
      style=NodeStyle(render_bounds_expand=None),
  )
  node.style.render_bounds_expand = Padding(left=22.0, right=22.0, top=29.0, bottom=29.0)
  width, height = _layout_slot_raster_emit_dimensions(node, 76.0, 76.0)
  assert width == 76.0
  assert height == 76.0
