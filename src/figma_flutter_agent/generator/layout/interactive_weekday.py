"""Weekday chip row Dart helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
    custom_code_zone_id,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.generator.layout.style.facts import contrast_label_on_surface_expr
from figma_flutter_agent.generator.layout.style.text_helpers import _flutter_font_weight_expr
from figma_flutter_agent.parser.interaction import (
    weekday_chip_initially_selected,
    weekday_chip_label,
)
from figma_flutter_agent.parser.interaction.chip_variant import (
    chip_circular_paint_surface,
    chip_circular_stroke_node,
)
from figma_flutter_agent.parser.interaction.shared import _MAX_LOCAL_DEPTH, _local_nodes
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_OUTLINE_FALLBACK = "Theme.of(context).colorScheme.outline"
_SURFACE_FALLBACK = "Theme.of(context).colorScheme.surface"
_DEFAULT_CHIP_SIZE = 40.7
_DEFAULT_CHIP_FONT_SIZE = 14.0


def weekday_chip_row_stateful_helpers(node_id: str) -> str:
    """Return Dart helper widgets for weekday chip rows."""
    zone = custom_code_zone_id(node_id, "weekday-chip")
    open_zone = block_custom_code_open(zone)
    close_zone = block_custom_code_close(zone)
    template = """
class _WeekdayChipSpec {
  const _WeekdayChipSpec({
    required this.label,
    required this.initiallySelected,
    required this.selectedBg,
    required this.unselectedBg,
    required this.selectedFg,
    required this.unselectedFg,
    required this.borderColor,
    required this.size,
    required this.fontSize,
    required this.fontWeight,
  });

  final String label;
  final bool initiallySelected;
  final Color selectedBg;
  final Color unselectedBg;
  final Color selectedFg;
  final Color unselectedFg;
  final Color borderColor;
  final double size;
  final double fontSize;
  final FontWeight fontWeight;
}

class _GeneratedWeekdayChipRow extends StatefulWidget {
  const _GeneratedWeekdayChipRow({required this.chips, super.key});

  final List<_WeekdayChipSpec> chips;

  @override
  State<_GeneratedWeekdayChipRow> createState() => _GeneratedWeekdayChipRowState();
}

class _GeneratedWeekdayChipRowState extends State<_GeneratedWeekdayChipRow> {
  late final List<bool> _selected = [
    for (final chip in widget.chips) chip.initiallySelected,
  ];

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        for (var index = 0; index < widget.chips.length; index++)
          _buildChip(context, index, textScaler),
      ],
    );
  }

  Widget _buildChip(BuildContext context, int index, TextScaler textScaler) {
    final chip = widget.chips[index];
    final selected = _selected[index];
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
            setState(() => _selected[index] = !selected);
            // <custom-code:__ZONE__>
            // </custom-code:__ZONE__>
          },
          customBorder: const CircleBorder(),
          child: Ink(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: bg,
              border: selected
                  ? null
                  : Border.all(color: chip.borderColor, width: 1.0),
            ),
            child: SizedBox(
              width: chip.size,
              height: chip.size,
              child: Center(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    chip.label,
                    maxLines: 1,
                    softWrap: false,
                    overflow: TextOverflow.clip,
                    style: TextStyle(
                      fontSize: chip.fontSize,
                      height: 1.0,
                      fontWeight: chip.fontWeight,
                      color: fg,
                    ),
                    textScaler: textScaler,
                    textAlign: TextAlign.center,
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


def _chip_label_text_node(chip: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    for item in _local_nodes(chip, _MAX_LOCAL_DEPTH):
        if item.type == NodeType.TEXT and item.text:
            return item
    return None


def _chip_label_style_fields(text_node: CleanDesignTreeNode | None) -> tuple[str, str]:
    if text_node is None:
        return (
            format_geometry_literal(_DEFAULT_CHIP_FONT_SIZE),
            "FontWeight.w500",
        )
    font_size = text_node.style.font_size
    size_lit = (
        format_geometry_literal(float(font_size))
        if font_size is not None and float(font_size) > 0
        else format_geometry_literal(_DEFAULT_CHIP_FONT_SIZE)
    )
    return size_lit, _flutter_font_weight_expr(text_node.style)


def _weekday_chip_border_expr(chip: CleanDesignTreeNode) -> str:
    stroke = chip_circular_stroke_node(chip)
    if stroke is not None:
        return dart_color_expr(
            stroke.style,
            css_key="border-color",
            fallback=_OUTLINE_FALLBACK,
        )
    paint = chip_circular_paint_surface(chip)
    if paint is not None:
        return dart_color_expr(
            paint.style,
            css_key="border-color",
            fallback=_OUTLINE_FALLBACK,
        )
    return dart_color_expr(
        chip.style,
        css_key="border-color",
        fallback=_OUTLINE_FALLBACK,
    )


def _weekday_chip_palette_exprs(
    chip: CleanDesignTreeNode,
    *,
    row_chips: list[CleanDesignTreeNode],
) -> tuple[str, str, str, str]:
    """Return selected/unselected background and foreground Dart color expressions."""
    _ = chip
    selected_ref = next(
        (item for item in row_chips if weekday_chip_initially_selected(item)),
        row_chips[0],
    )
    unselected_ref = next(
        (item for item in row_chips if not weekday_chip_initially_selected(item)),
        row_chips[0],
    )
    sel_paint = chip_circular_paint_surface(selected_ref) or selected_ref
    uns_paint = chip_circular_paint_surface(unselected_ref)
    uns_stroke = chip_circular_stroke_node(unselected_ref)

    selected_bg = dart_color_expr(sel_paint.style, fallback=_SURFACE_FALLBACK)
    if uns_paint is not None and uns_paint.style.background_color:
        unselected_bg = dart_color_expr(uns_paint.style, fallback=_SURFACE_FALLBACK)
    else:
        unselected_bg = _SURFACE_FALLBACK

    selected_fg = contrast_label_on_surface_expr(sel_paint.style.background_color)
    if uns_stroke is not None:
        unselected_fg = dart_color_expr(
            uns_stroke.style,
            css_key="border-color",
            fallback="Theme.of(context).colorScheme.onSurfaceVariant",
        )
    elif uns_paint is not None:
        unselected_fg = contrast_label_on_surface_expr(uns_paint.style.background_color)
    else:
        unselected_fg = "Theme.of(context).colorScheme.onSurfaceVariant"

    return selected_bg, unselected_bg, selected_fg, unselected_fg


def _weekday_chip_size(chip: CleanDesignTreeNode) -> float:
    width = chip.sizing.width
    height = chip.sizing.height
    if width is not None and height is not None and width > 0 and height > 0:
        return float(min(width, height))
    if width is not None and width > 0:
        return float(width)
    if height is not None and height > 0:
        return float(height)
    return _DEFAULT_CHIP_SIZE


def render_weekday_chip_row(node: CleanDesignTreeNode) -> str:
    """Render a row of tappable weekday chips with selection state."""
    row_chips = sorted(
        node.children,
        key=lambda item: (
            float(item.stack_placement.left or 0.0) if item.stack_placement is not None else 0.0
        ),
    )
    specs: list[str] = []
    for chip in row_chips:
        label = weekday_chip_label(chip)
        if not label:
            continue
        selected = weekday_chip_initially_selected(chip)
        selected_bg, unselected_bg, selected_fg, unselected_fg = _weekday_chip_palette_exprs(
            chip,
            row_chips=row_chips,
        )
        border_expr = _weekday_chip_border_expr(chip)
        text_node = _chip_label_text_node(chip)
        font_size_lit, font_weight_expr = _chip_label_style_fields(text_node)
        chip_size = format_geometry_literal(_weekday_chip_size(chip))
        specs.append(
            "_WeekdayChipSpec("
            f"label: '{escape_dart_string(label)}', "
            f"initiallySelected: {str(selected).lower()}, "
            f"selectedBg: {selected_bg}, "
            f"unselectedBg: {unselected_bg}, "
            f"selectedFg: {selected_fg}, "
            f"unselectedFg: {unselected_fg}, "
            f"borderColor: {border_expr}, "
            f"size: {chip_size}, "
            f"fontSize: {font_size_lit}, "
            f"fontWeight: {font_weight_expr}"
            ")"
        )
    return f"_GeneratedWeekdayChipRow(chips: [{', '.join(specs)}])"
