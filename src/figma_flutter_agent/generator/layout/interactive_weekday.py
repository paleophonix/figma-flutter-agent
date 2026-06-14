"""Weekday chip row Dart helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
    custom_code_zone_id,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style.colors import (
    dart_color_expr,
    is_dark_fill_color,
)
from figma_flutter_agent.generator.layout.style.facts import label_color_on_surface_expr
from figma_flutter_agent.parser.interaction import (
    weekday_chip_initially_selected,
    weekday_chip_label,
)
from figma_flutter_agent.parser.interaction.shared import _MAX_LOCAL_DEPTH, _local_nodes
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType

_OUTLINE_FALLBACK = "Theme.of(context).colorScheme.outline"
_SURFACE_FALLBACK = "Theme.of(context).colorScheme.surface"
_INVERSE_SURFACE_FALLBACK = "Theme.of(context).colorScheme.inverseSurface"
_DEFAULT_CHIP_SIZE = 40.7


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
    required this.fillColor,
    required this.textColor,
    required this.borderColor,
    required this.size,
  });

  final String label;
  final bool initiallySelected;
  final Color fillColor;
  final Color textColor;
  final Color borderColor;
  final double size;
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
              color: selected ? chip.fillColor : chip.borderColor,
              border: Border.all(color: chip.borderColor, width: 1.0),
            ),
            child: SizedBox(
              width: chip.size,
              height: chip.size,
              child: Center(
                child: Text(
                  chip.label,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: chip.textColor,
                      ),
                  textScaler: textScaler,
                  textAlign: TextAlign.center,
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


def _chip_surface_style(
    chip: CleanDesignTreeNode,
    *,
    prefer_dark: bool,
) -> NodeStyle:
    candidates = [chip, *chip.children]
    if prefer_dark:
        for item in candidates:
            if is_dark_fill_color(item.style.background_color):
                return item.style
    for item in candidates:
        if item.style.background_color:
            return item.style
    return chip.style


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
    specs: list[str] = []
    for chip in sorted(
        node.children,
        key=lambda item: float(item.stack_placement.left or 0.0)
        if item.stack_placement is not None
        else 0.0,
    ):
        label = weekday_chip_label(chip)
        if not label:
            continue
        selected = weekday_chip_initially_selected(chip)
        dark_style = _chip_surface_style(chip, prefer_dark=True)
        light_style = _chip_surface_style(chip, prefer_dark=False)
        fill_expr = dart_color_expr(
            dark_style,
            fallback=_INVERSE_SURFACE_FALLBACK,
        )
        border_expr = dart_color_expr(
            chip.style,
            css_key="border-color",
            fallback=_OUTLINE_FALLBACK,
        )
        text_node = _chip_label_text_node(chip)
        surface_color = (
            dark_style.background_color if selected else light_style.background_color
        )
        if text_node is not None:
            text_expr = label_color_on_surface_expr(
                text_node.style,
                surface_color=surface_color,
            )
        else:
            text_expr = dart_color_expr(
                chip.style,
                css_key="color",
                fallback="Theme.of(context).colorScheme.onSurfaceVariant",
            )
        chip_size = format_geometry_literal(_weekday_chip_size(chip))
        specs.append(
            "_WeekdayChipSpec("
            f"label: '{escape_dart_string(label)}', "
            f"initiallySelected: {str(selected).lower()}, "
            f"fillColor: {fill_expr}, "
            f"textColor: {text_expr}, "
            f"borderColor: {border_expr}, "
            f"size: {chip_size}"
            ")"
        )
    body = f"_GeneratedWeekdayChipRow(chips: [{', '.join(specs)}])"
    placement = node.stack_placement
    if placement is None:
        return body
    fields: list[str] = []
    if placement.left is not None:
        fields.append(f"left: {format_geometry_literal(placement.left)}")
    if placement.top is not None:
        fields.append(f"top: {format_geometry_literal(placement.top)}")
    width = placement.width if placement.width is not None else node.sizing.width
    if width is not None and width > 0:
        fields.append(f"width: {format_geometry_literal(width)}")
    height = placement.height if placement.height is not None else node.sizing.height
    if height is not None and height > 0:
        fields.append(f"height: {format_geometry_literal(height)}")
    if not fields:
        return body
    return f"Positioned({', '.join(fields)}, child: {body})"
