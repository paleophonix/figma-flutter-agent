"""Regression laws from niyama_order batch repair (generic, not screen-patched)."""

from __future__ import annotations

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
from figma_flutter_agent.parser.interaction.product import (
    _stack_hosts_horizontal_product_carrier_row,
    layout_fact_stack_detail_hero_banner_host,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
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
