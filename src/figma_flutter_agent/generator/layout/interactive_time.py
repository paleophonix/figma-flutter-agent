"""Time wheel picker Dart helpers."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
    custom_code_zone_id,
)
from figma_flutter_agent.parser.interaction import _wheel_picker_text_nodes
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass(frozen=True)
class WheelPickerColumn:
    """One wheel picker column."""

    labels: tuple[str, ...]
    selected_index: int
    font_size: float | None = None


def extract_wheel_picker_columns(node: CleanDesignTreeNode) -> list[WheelPickerColumn]:
    """Cluster wheel labels into columns ordered left-to-right."""
    texts = _wheel_picker_text_nodes(node)
    if not texts:
        return []
    picker_top = (
        float(node.stack_placement.top)
        if node.stack_placement and node.stack_placement.top
        else 0.0
    )
    picker_height = float(node.sizing.height or 0)
    picker_mid_y = picker_top + picker_height / 2.0 if picker_height > 0 else picker_top

    buckets: dict[int, list[CleanDesignTreeNode]] = {}
    for text_node in texts:
        placement = text_node.stack_placement
        left = (
            placement.left
            if placement is not None and placement.left is not None
            else text_node.offset_x
        )
        bucket_key = int(round(float(left or 0.0) / 8.0) * 8)
        buckets.setdefault(bucket_key, []).append(text_node)

    columns: list[WheelPickerColumn] = []
    for bucket_key in sorted(buckets):
        ordered = sorted(
            buckets[bucket_key],
            key=lambda item: (
                float(item.stack_placement.top or 0.0) if item.stack_placement is not None else 0.0
            ),
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
            text_mid = (
                float(placement.top) + float(placement.height or text_node.sizing.height or 0) / 2.0
            )
            distance = abs(text_mid - picker_mid_y)
            if distance < best_distance:
                best_distance = distance
                selected_index = index
        font_sizes = [
            float(item.style.font_size) for item in ordered if item.style.font_size is not None
        ]
        column_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else None
        columns.append(
            WheelPickerColumn(
                labels=labels,
                selected_index=selected_index,
                font_size=column_font_size,
            )
        )
    return columns


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
    this.fontSize,
  });

  final List<String> labels;
  final int initialIndex;
  final double? fontSize;
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
                              fontSize: widget.columns[index].fontSize,
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


def render_time_wheel_picker_stack(node: CleanDesignTreeNode) -> str:
    """Render a Cupertino-style scroll wheel extracted from Figma text columns."""
    columns = extract_wheel_picker_columns(node)
    if not columns:
        return "const SizedBox.shrink()"
    column_specs = ", ".join(
        "_WheelPickerColumnSpec("
        f"labels: [{', '.join(repr(label) for label in column.labels)}], "
        f"initialIndex: {column.selected_index}"
        + (
            f", fontSize: {format_geometry_literal(column.font_size)}"
            if column.font_size is not None
            else ""
        )
        + ")"
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
