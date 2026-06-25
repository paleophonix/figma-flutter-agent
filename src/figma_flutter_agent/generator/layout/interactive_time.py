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


_WHEEL_COLUMN_MERGE_GAP_PX = 48.0


def _wheel_text_left(text_node: CleanDesignTreeNode) -> float:
    placement = text_node.stack_placement
    if placement is not None and placement.left is not None:
        return float(placement.left)
    return float(text_node.offset_x or 0.0)


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

    ordered_texts = sorted(texts, key=_wheel_text_left)
    clusters: list[list[CleanDesignTreeNode]] = []
    cluster_centers: list[float] = []
    for text_node in ordered_texts:
        left = _wheel_text_left(text_node)
        placed = False
        for index, center in enumerate(cluster_centers):
            if abs(left - center) <= _WHEEL_COLUMN_MERGE_GAP_PX:
                clusters[index].append(text_node)
                cluster_centers[index] = sum(_wheel_text_left(item) for item in clusters[index]) / len(
                    clusters[index]
                )
                placed = True
                break
        if not placed:
            clusters.append([text_node])
            cluster_centers.append(left)

    columns_with_left: list[tuple[float, WheelPickerColumn]] = []
    for cluster, center in zip(clusters, cluster_centers, strict=True):
        ordered = sorted(
            cluster,
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
        columns_with_left.append(
            (
                center,
                WheelPickerColumn(
                    labels=labels,
                    selected_index=selected_index,
                    font_size=column_font_size,
                ),
            )
        )
    columns_with_left.sort(key=lambda item: item[0])
    return [column for _, column in columns_with_left]


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
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Row(
            children: [
              for (var index = 0; index < widget.columns.length; index++)
                Expanded(
                  child: CupertinoPicker(
                    scrollController: _controllers[index],
                    itemExtent: 40.0,
                    magnification: 1.0,
                    squeeze: 1.0,
                    useMagnifier: false,
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
          Positioned.fill(
            child: IgnorePointer(
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: double.infinity,
                      height: 1.0,
                      color: const Color(0xFFD0D0D8),
                    ),
                    const SizedBox(height: 40.0),
                    Container(
                      width: double.infinity,
                      height: 1.0,
                      color: const Color(0xFFD0D0D8),
                    ),
                  ],
                ),
              ),
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
    return f"_GeneratedTimeWheelPicker(columns: [{column_specs}], height: {height})"
