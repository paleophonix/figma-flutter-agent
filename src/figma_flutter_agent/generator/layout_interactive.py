"""Stateful interactive controls for deterministic layout (pickers, weekday chips)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
    custom_code_zone_id,
)
from figma_flutter_agent.generator.layout_common import escape_dart_string
from figma_flutter_agent.parser.interaction import (
    WEEKDAY_CHIP_ROW_NAME,
    _wheel_picker_text_nodes,
    looks_like_wheel_time_picker_stack,
    weekday_chip_initially_selected,
    weekday_chip_label,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass(frozen=True)
class _WheelPickerColumn:
    labels: tuple[str, ...]
    selected_index: int


def extract_wheel_picker_columns(node: CleanDesignTreeNode) -> list[_WheelPickerColumn]:
    """Cluster wheel labels into columns ordered left-to-right."""
    texts = _wheel_picker_text_nodes(node)
    if not texts:
        return []
    picker_top = float(node.stack_placement.top) if node.stack_placement and node.stack_placement.top else 0.0
    picker_height = float(node.sizing.height or 0)
    picker_mid_y = picker_top + picker_height / 2.0 if picker_height > 0 else picker_top

    buckets: dict[int, list[CleanDesignTreeNode]] = {}
    for text_node in texts:
        placement = text_node.stack_placement
        left = placement.left if placement is not None and placement.left is not None else text_node.offset_x
        bucket_key = int(round(float(left or 0.0) / 8.0) * 8)
        buckets.setdefault(bucket_key, []).append(text_node)

    columns: list[_WheelPickerColumn] = []
    for bucket_key in sorted(buckets):
        ordered = sorted(
            buckets[bucket_key],
            key=lambda item: float(item.stack_placement.top or 0.0)
            if item.stack_placement is not None
            else 0.0,
        )
        labels = tuple((item.text or "").strip() for item in ordered if (item.text or "").strip())
        if not labels:
            continue
        selected_index = 0
        best_distance = float("inf")
        for index, text_node in enumerate(ordered):
            placement = text_node.stack_placement
            if placement is None or placement.top is None:
                continue
            text_mid = float(placement.top) + float(placement.height or text_node.sizing.height or 0) / 2.0
            distance = abs(text_mid - picker_mid_y)
            if distance < best_distance:
                best_distance = distance
                selected_index = index
        columns.append(_WheelPickerColumn(labels=labels, selected_index=selected_index))
    return columns


def layout_interactive_helpers_needed(tree: CleanDesignTreeNode) -> bool:
    """Return True when generated layout needs interactive helper widgets."""

    def walk(node: CleanDesignTreeNode) -> bool:
        if node.name == WEEKDAY_CHIP_ROW_NAME:
            return True
        if looks_like_wheel_time_picker_stack(node):
            return True
        return any(walk(child) for child in node.children)

    return walk(tree)


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


def time_wheel_picker_stateful_helpers(node_id: str) -> str:
    """Return Dart helper widgets for scrollable time wheels."""
    zone = custom_code_zone_id(node_id, "time-wheel")
    open_zone = block_custom_code_open(zone)
    close_zone = block_custom_code_close(zone)
    template = """
class _WheelPickerColumnSpec {
  const _WheelPickerColumnSpec({
    required this.labels,
    required this.initialIndex,
  });

  final List<String> labels;
  final int initialIndex;
}

class _GeneratedTimeWheelPicker extends StatefulWidget {
  const _GeneratedTimeWheelPicker({
    required this.columns,
    required this.height,
    super.key,
  });

  final List<_WheelPickerColumnSpec> columns;
  final double height;

  @override
  State<_GeneratedTimeWheelPicker> createState() => _GeneratedTimeWheelPickerState();
}

class _GeneratedTimeWheelPickerState extends State<_GeneratedTimeWheelPicker> {
  late final List<FixedExtentScrollController> _controllers = [
    for (final column in widget.columns)
      FixedExtentScrollController(initialItem: column.initialIndex),
  ];

  @override
  void dispose() {
    for (final controller in _controllers) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return SizedBox(
      height: widget.height,
      child: Row(
        children: [
          for (var index = 0; index < widget.columns.length; index++)
            Expanded(
              child: CupertinoPicker(
                scrollController: _controllers[index],
                itemExtent: 40.0,
                magnification: 1.05,
                squeeze: 1.1,
                useMagnifier: true,
                onSelectedItemChanged: (_) {
                  // <custom-code:__ZONE__>
                  // </custom-code:__ZONE__>
                },
                children: [
                  for (final label in widget.columns[index].labels)
                    Center(
                      child: Text(
                        label,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontSize: 24.0,
                              fontWeight: FontWeight.w400,
                            ),
                        textScaler: textScaler,
                      ),
                    ),
                ],
              ),
            ),
        ],
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


def render_time_wheel_picker_stack(node: CleanDesignTreeNode) -> str:
    """Render a Cupertino-style scroll wheel extracted from Figma text columns."""
    columns = extract_wheel_picker_columns(node)
    if not columns:
        return "const SizedBox.shrink()"
    column_specs = ", ".join(
        "_WheelPickerColumnSpec("
        f"labels: [{', '.join(repr(label) for label in column.labels)}], "
        f"initialIndex: {column.selected_index}"
        ")"
        for column in columns
    )
    height = float(node.sizing.height or 192.0)
    body = f"_GeneratedTimeWheelPicker(columns: [{column_specs}], height: {height})"
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
    if placement.height is not None and placement.height > 0:
        fields.append(f"height: {format_geometry_literal(placement.height)}")
    elif node.sizing.height is not None and node.sizing.height > 0:
        fields.append(f"height: {format_geometry_literal(node.sizing.height)}")
    if not fields:
        return body
    return f"Positioned({', '.join(fields)}, child: {body})"


def interactive_layout_helpers(tree: CleanDesignTreeNode) -> str:
    """Compose all Dart helper classes required by ``tree``."""
    weekday_node_id: str | None = None
    wheel_node_id: str | None = None

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal weekday_node_id, wheel_node_id
        if weekday_node_id is None and node.name == WEEKDAY_CHIP_ROW_NAME:
            weekday_node_id = node.id
        if wheel_node_id is None and looks_like_wheel_time_picker_stack(node):
            wheel_node_id = node.id
        for child in node.children:
            walk(child)

    walk(tree)
    blocks: list[str] = []
    if weekday_node_id is not None:
        blocks.append(weekday_chip_row_stateful_helpers(weekday_node_id))
    if wheel_node_id is not None:
        blocks.append(time_wheel_picker_stateful_helpers(wheel_node_id))
    return "\n".join(blocks)
