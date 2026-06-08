"""Weekday chip row Dart helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
    custom_code_zone_id,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.parser.interaction import (
    weekday_chip_initially_selected,
    weekday_chip_label,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode


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
  });

  final String label;
  final bool initiallySelected;
  final Color fillColor;
  final Color textColor;
  final Color borderColor;
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
              width: 40.7,
              height: 40.7,
              child: Center(
                child: Text(
                  chip.label,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: selected ? chip.textColor : chip.textColor,
                        fontSize: 14.0,
                        fontWeight: FontWeight.w700,
                        height: 1.65,
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
        fill = "0xFF3F414E" if selected else "0xFFFFFFFF"
        text = "0xFFFEFFFE" if selected else "0xFFA1A4B2"
        border = "0xFFE6E7F2"
        specs.append(
            "_WeekdayChipSpec("
            f"label: '{escape_dart_string(label)}', "
            f"initiallySelected: {str(selected).lower()}, "
            f"fillColor: Color({fill}), "
            f"textColor: Color({text}), "
            f"borderColor: Color({border})"
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
