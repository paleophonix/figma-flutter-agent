"""Stateful segmented pill control helpers for generated Dart."""

from __future__ import annotations


def segmented_pill_stateful_helpers() -> str:
    """Return Dart source for ``_SegmentedPillControl`` stateful segmented host."""
    return """
class _SegmentedPillControl extends StatefulWidget {
  const _SegmentedPillControl({
    required this.labels,
    required this.initialIndex,
    super.key,
  });

  final List<String> labels;
  final int initialIndex;

  @override
  State<_SegmentedPillControl> createState() => _SegmentedPillControlState();
}

class _SegmentedPillControlState extends State<_SegmentedPillControl> {
  late int _selectedIndex = widget.initialIndex;

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        for (var index = 0; index < widget.labels.length; index++)
          Expanded(
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => setState(() => _selectedIndex = index),
              child: Center(
                child: Text(
                  widget.labels[index],
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: _selectedIndex == index
                            ? Theme.of(context).colorScheme.onPrimaryContainer
                            : Theme.of(context).colorScheme.onSurfaceVariant,
                        fontWeight:
                            _selectedIndex == index ? FontWeight.w600 : FontWeight.w400,
                      ),
                  textScaler: textScaler,
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ),
      ],
    );
  }
}
"""
