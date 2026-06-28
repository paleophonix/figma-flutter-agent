"""Foreign delegate inline must preserve host structural chrome."""

from figma_flutter_agent.generator.planned.reconcile.class_inspect import (
    _host_has_structural_chrome,
    _is_foreign_delegate_widget_build,
)
from figma_flutter_agent.generator.planned.reconcile.delegate_repair import (
    repair_foreign_delegate_widget_builds,
    repair_stale_widget_ctor_names_in_planned,
)


def test_host_with_title_row_is_not_foreign_delegate() -> None:
    content = """
class SectionHeaderWidget extends StatelessWidget {
  const SectionHeaderWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return Container(
      child: Row(
        children: [
          Expanded(child: Text('SECTION HEADER')),
          const ClusterChipWidget(),
        ],
      ),
    );
  }
}
"""
    assert not _is_foreign_delegate_widget_build(content, "SectionHeaderWidget")
    assert _host_has_structural_chrome(
        "return Container(child: Row(children: [Expanded(child: Text('x')), const ClusterChipWidget()]))",
        "SectionHeaderWidget",
    )


def test_foreign_delegate_inline_preserves_structural_host() -> None:
    planned = {
        "lib/widgets/section_header_widget.dart": """
import 'package:flutter/material.dart';
import 'package:demo_app/widgets/cluster_chip_widget.dart';

class SectionHeaderWidget extends StatelessWidget {
  const SectionHeaderWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 390.0,
      height: 72.0,
      child: Row(
        children: [
          const Expanded(child: Text('SECTION HEADER')),
          const ClusterChipWidget(),
        ],
      ),
    );
  }
}
""",
        "lib/widgets/cluster_chip_widget.dart": """
class ClusterChipWidget extends StatelessWidget {
  const ClusterChipWidget({super.key});
  @override
  Widget build(BuildContext context) => const Text('View all');
}
""",
    }
    updated = repair_foreign_delegate_widget_builds(planned)
    header = updated["lib/widgets/section_header_widget.dart"]
    assert "SECTION HEADER" in header
    assert "View all" in header or "ClusterChipWidget" in header

    pruned = dict(updated)
    pruned.pop("lib/widgets/cluster_chip_widget.dart", None)
    repaired = repair_stale_widget_ctor_names_in_planned(pruned)
    header_after = repaired["lib/widgets/section_header_widget.dart"]
    assert "SECTION HEADER" in header_after
    assert "ClusterChipWidget" not in header_after
    assert "SizedBox.shrink" in header_after


def test_bare_delegate_still_inlines() -> None:
    planned = {
        "lib/widgets/wrapper_widget.dart": """
class WrapperWidget extends StatelessWidget {
  const WrapperWidget({super.key});
  @override
  Widget build(BuildContext context) => const TargetWidget();
}
""",
        "lib/widgets/target_widget.dart": """
class TargetWidget extends StatelessWidget {
  const TargetWidget({super.key});
  @override
  Widget build(BuildContext context) => const Text('ok');
}
""",
    }
    updated = repair_foreign_delegate_widget_builds(planned)
    wrapper = updated["lib/widgets/wrapper_widget.dart"]
    assert "TargetWidget" not in wrapper
    assert "Text('ok')" in wrapper
