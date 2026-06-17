"""Stateful circular option chip rows (size / dimension pickers)."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
    custom_code_zone_id,
)
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    layout_fact_stack_circular_option_glyph_host,
)
from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.generator.layout.style.facts import contrast_label_on_surface_expr
from figma_flutter_agent.parser.interaction.chip_variant import (
    chip_component_display_label,
    chip_component_label_text_node,
    chip_component_paint_surface,
    chip_component_selected,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_SURFACE_FALLBACK = "Theme.of(context).colorScheme.surfaceContainerHighest"


def layout_fact_circular_option_chip_row_host(node: CleanDesignTreeNode) -> bool:
    """Return True when a STACK hosts two or more circular option chips in a row."""
    if node.type != NodeType.STACK:
        return False
    chip_children = [
        child for child in node.children if layout_fact_stack_circular_option_glyph_host(child)
    ]
    return len(chip_children) >= 2


def circular_chip_row_host_section_labels(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Return direct TEXT captions on a circular chip row host (for example ``Size:``)."""
    return [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]


def _section_label_vertical_bottom(label: CleanDesignTreeNode) -> float:
    """Return the bottom edge of a section label in host stack coordinates."""
    placement = label.stack_placement
    top = float(placement.top or 0.0) if placement is not None else 0.0
    height = float(label.sizing.height or 0.0)
    if height <= 0.0 and placement is not None and placement.height is not None:
        height = float(placement.height)
    return top + height


def _chip_row_band_top(node: CleanDesignTreeNode) -> float:
    """Return the top edge of the circular chip band inside a chip-row host."""
    tops: list[float] = []
    for child in node.children:
        if not layout_fact_stack_circular_option_glyph_host(child):
            continue
        placement = child.stack_placement
        tops.append(float(placement.top or 0.0) if placement is not None else 0.0)
    return min(tops) if tops else 0.0


def _chip_row_band_left(node: CleanDesignTreeNode) -> float:
    """Return the left edge of the circular chip band inside a chip-row host."""
    lefts: list[float] = []
    for child in node.children:
        if not layout_fact_stack_circular_option_glyph_host(child):
            continue
        placement = child.stack_placement
        lefts.append(float(placement.left or 0.0) if placement is not None else 0.0)
    return min(lefts) if lefts else 0.0


def circular_chip_row_section_labels_overlap_chips(
    node: CleanDesignTreeNode,
    labels: list[CleanDesignTreeNode],
) -> bool:
    """Return True when section captions overlap the chip band in absolute host geometry."""
    chip_top = _chip_row_band_top(node)
    return any(_section_label_vertical_bottom(label) > chip_top + 0.5 for label in labels)


def render_circular_chip_row_host_shell(
    node: CleanDesignTreeNode,
    *,
    chip_row: str,
    label_widgets: list[str],
    section_labels: list[CleanDesignTreeNode],
) -> str:
    """Compose chip row hosts with section captions using flow or overlay layout."""
    if not section_labels or not label_widgets:
        return chip_row
    if circular_chip_row_section_labels_overlap_chips(node, section_labels):
        host_width = float(node.sizing.width or 0.0)
        host_height = float(node.sizing.height or 0.0)
        chip_left_lit = format_geometry_literal(_chip_row_band_left(node))
        chip_top_lit = format_geometry_literal(_chip_row_band_top(node))
        chip_child = f"Positioned(left: {chip_left_lit}, top: {chip_top_lit}, child: {chip_row})"
        inner = (
            f"Stack(clipBehavior: Clip.none, children: [{', '.join([*label_widgets, chip_child])}])"
        )
        if host_width > 0.0 and host_height > 0.0:
            return (
                f"SizedBox(width: {format_geometry_literal(host_width)}, "
                f"height: {format_geometry_literal(host_height)}, child: {inner})"
            )
        return inner
    return (
        "Column("
        "mainAxisSize: MainAxisSize.min, "
        "crossAxisAlignment: CrossAxisAlignment.start, "
        f"children: [{', '.join([*label_widgets, chip_row])}]"
        ")"
    )


def circular_option_chip_row_stateful_helpers(node_id: str) -> str:
    """Return Dart helper widgets for mutually exclusive circular option chip rows."""
    zone = custom_code_zone_id(node_id, "chip-choice")
    open_zone = block_custom_code_open(zone)
    close_zone = block_custom_code_close(zone)
    template = """
class _CircularOptionChipSpec {
  const _CircularOptionChipSpec({
    required this.label,
    required this.initiallySelected,
    required this.selectedBg,
    required this.unselectedBg,
    required this.selectedFg,
    required this.unselectedFg,
    required this.radius,
    required this.size,
  });

  final String label;
  final bool initiallySelected;
  final Color selectedBg;
  final Color unselectedBg;
  final Color selectedFg;
  final Color unselectedFg;
  final double radius;
  final double size;
}

class _GeneratedCircularOptionChipRow extends StatefulWidget {
  const _GeneratedCircularOptionChipRow({required this.chips, super.key});

  final List<_CircularOptionChipSpec> chips;

  @override
  State<_GeneratedCircularOptionChipRow> createState() =>
      _GeneratedCircularOptionChipRowState();
}

class _GeneratedCircularOptionChipRowState extends State<_GeneratedCircularOptionChipRow> {
  late int _selectedIndex;

  @override
  void initState() {
    super.initState();
    final initial = widget.chips.indexWhere((chip) => chip.initiallySelected);
    _selectedIndex = initial >= 0 ? initial : 0;
  }

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.start,
      children: [
        for (var index = 0; index < widget.chips.length; index++)
          Padding(
            padding: EdgeInsets.only(right: index + 1 < widget.chips.length ? 12.0 : 0.0),
            child: _buildChip(context, index, textScaler),
          ),
      ],
    );
  }

  Widget _buildChip(BuildContext context, int index, TextScaler textScaler) {
    final chip = widget.chips[index];
    final selected = _selectedIndex == index;
    final bg = selected ? chip.selectedBg : chip.unselectedBg;
    final fg = selected ? chip.selectedFg : chip.unselectedFg;
    return Semantics(
      label: chip.label,
      button: true,
      selected: selected,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            setState(() => _selectedIndex = index);
            // <custom-code:__ZONE__>
            // </custom-code:__ZONE__>
          },
          customBorder: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(chip.radius),
          ),
          child: Ink(
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(chip.radius),
            ),
            child: SizedBox(
              width: chip.size,
              height: chip.size,
              child: ClipRect(
                child: Align(
                  alignment: Alignment.center,
                  child: Text(
                    chip.label,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: fg),
                    textScaler: textScaler,
                    textAlign: TextAlign.center,
                    maxLines: 1,
                    overflow: TextOverflow.clip,
                    softWrap: false,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
"""
    return template.replace("// <custom-code:__ZONE__>", open_zone).replace(
        "// </custom-code:__ZONE__>", close_zone
    )


def _chip_palette_exprs(
    chip: CleanDesignTreeNode,
    *,
    row_chips: list[CleanDesignTreeNode],
) -> tuple[str, str, str, str]:
    """Return selected/unselected background and foreground Dart color expressions."""
    _ = chip
    selected_ref = next((item for item in row_chips if chip_component_selected(item)), row_chips[0])
    unselected_ref = next(
        (item for item in row_chips if not chip_component_selected(item)),
        row_chips[0],
    )
    sel_surface = chip_component_paint_surface(selected_ref) or selected_ref
    uns_surface = chip_component_paint_surface(unselected_ref) or unselected_ref
    selected_bg = dart_color_expr(sel_surface.style, fallback=_SURFACE_FALLBACK)
    unselected_bg = dart_color_expr(uns_surface.style, fallback=_SURFACE_FALLBACK)
    selected_fg = contrast_label_on_surface_expr(sel_surface.style.background_color)
    unselected_fg = contrast_label_on_surface_expr(uns_surface.style.background_color)
    return selected_bg, unselected_bg, selected_fg, unselected_fg


def _chip_size_literal(chip: CleanDesignTreeNode) -> str:
    width = chip.sizing.width
    height = chip.sizing.height
    if width is not None and height is not None and float(width) > 0 and float(height) > 0:
        return format_geometry_literal(min(float(width), float(height)))
    if width is not None and float(width) > 0:
        return format_geometry_literal(float(width))
    return "48.0"


def render_circular_option_chip_row_stateful(
    node: CleanDesignTreeNode,
    ctx: IrEmitContext | None = None,
) -> str:
    """Render a row of mutually exclusive circular option chips with tap selection."""
    _ = ctx
    chips = sorted(
        (child for child in node.children if layout_fact_stack_circular_option_glyph_host(child)),
        key=lambda item: (
            float(item.stack_placement.left or 0.0) if item.stack_placement is not None else 0.0
        ),
    )
    specs: list[str] = []
    for chip in chips:
        label = chip_component_display_label(chip)
        if not label:
            text_node = chip_component_label_text_node(chip)
            label = (text_node.text or "").strip() if text_node is not None else ""
        if not label:
            continue
        surface = chip_component_paint_surface(chip) or chip
        radius = surface.style.border_radius or chip.style.border_radius or 24.0
        selected_bg, unselected_bg, selected_fg, unselected_fg = _chip_palette_exprs(
            chip,
            row_chips=chips,
        )
        specs.append(
            "_CircularOptionChipSpec("
            f"label: '{escape_dart_string(label)}', "
            f"initiallySelected: {str(chip_component_selected(chip)).lower()}, "
            f"selectedBg: {selected_bg}, "
            f"unselectedBg: {unselected_bg}, "
            f"selectedFg: {selected_fg}, "
            f"unselectedFg: {unselected_fg}, "
            f"radius: {format_geometry_literal(float(radius))}, "
            f"size: {_chip_size_literal(chip)}"
            ")"
        )
    return f"_GeneratedCircularOptionChipRow(chips: [{', '.join(specs)}])"
