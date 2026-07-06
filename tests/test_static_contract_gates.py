"""Regression tests for static planned-Dart contract gates."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import PlannedDartGraphError
from figma_flutter_agent.generator.dart import static_contract_gates
from figma_flutter_agent.generator.dart.static_contract_gates import (
    find_planned_widget_invocation_cycles,
    find_widget_callsite_constructor_mismatches,
    gate_disk_widget_import_closure,
    run_static_contract_gates,
)
from figma_flutter_agent.generator.planned.reconcile import reconcile_planned_dart_files


def test_static_contract_gates_binds_nested_flex_collector_at_import() -> None:
    """Gate module must bind wrap.collect_nested_flex_parent_data_spans at import time."""
    assert static_contract_gates.collect_nested_flex_parent_data_spans is not None


def test_planned_widget_graph_acyclic_gate_detects_mutual_invocation() -> None:
    planned = {
        "lib/widgets/a_widget.dart": """
class AWidget extends StatelessWidget {
  const AWidget({super.key});
  @override
  Widget build(BuildContext context) => const BWidget();
}
""",
        "lib/widgets/b_widget.dart": """
class BWidget extends StatelessWidget {
  const BWidget({super.key});
  @override
  Widget build(BuildContext context) => const AWidget();
}
""",
    }
    cycles = find_planned_widget_invocation_cycles(planned)
    assert cycles
    with pytest.raises(PlannedDartGraphError, match="planned_widget_graph_acyclic"):
        run_static_contract_gates(planned)


def test_widget_callsite_matches_constructor_gate_flags_unknown_named_arg() -> None:
    planned = {
        "lib/widgets/chip_widget.dart": """
class ChipWidget extends StatelessWidget {
  const ChipWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}
""",
        "lib/generated/demo_layout.dart": """
class DemoLayout extends StatelessWidget {
  const DemoLayout({super.key});
  @override
  Widget build(BuildContext context) => const ChipWidget(label: 'x');
}
""",
    }
    mismatches = find_widget_callsite_constructor_mismatches(planned)
    assert any("label" in item for item in mismatches)
    with pytest.raises(PlannedDartGraphError, match="widget_callsite_matches_constructor"):
        run_static_contract_gates(planned)


def test_nested_flex_parent_data_gate_flags_flexible_expanded() -> None:
    from figma_flutter_agent.generator.dart.static_contract_gates import (
        find_nested_flex_parent_data_wrappers,
    )

    planned = {
        "lib/widgets/header_widget.dart": """
class HeaderWidget extends StatelessWidget {
  const HeaderWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Flexible(fit: FlexFit.loose, flex: 0, child: Expanded(child: SizedBox(child: Text('x')))),
    ]);
  }
}
""",
    }
    violations = find_nested_flex_parent_data_wrappers(planned)
    assert violations
    with pytest.raises(
        PlannedDartGraphError,
        match="generated_dart_must_not_contain_nested_flex_parent_data_wrappers",
    ):
        run_static_contract_gates(planned)


def test_nested_flex_parent_data_gate_flags_flexible_inside_expanded() -> None:
    from figma_flutter_agent.generator.dart.static_contract_gates import (
        find_nested_flex_parent_data_wrappers,
    )

    planned = {
        "lib/widgets/paywall_status_bar_widget.dart": """
class PaywallStatusBarWidget extends StatelessWidget {
  const PaywallStatusBarWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Expanded(child: SizedBox(child: Stack(children: [
        Row(children: [
          Flexible(fit: FlexFit.loose, flex: 0, child: Flexible(fit: FlexFit.loose, flex: 0, child: SizedBox(child: Text('9:30')))),
        ]),
      ]))),
    ]);
  }
}
""",
    }
    violations = find_nested_flex_parent_data_wrappers(planned)
    assert violations
    assert "paywall_status_bar_widget.dart" in violations[0]


def test_reconcile_repairs_nested_flex_before_static_gate() -> None:
    planned = {
        "lib/widgets/header_widget.dart": """
class HeaderWidget extends StatelessWidget {
  const HeaderWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Flexible(fit: FlexFit.loose, flex: 0, child: Expanded(child: SizedBox(child: Text('x')))),
    ]);
  }
}
""",
    }
    updated = reconcile_planned_dart_files(planned, package_name="demo")
    body = updated["lib/widgets/header_widget.dart"]
    assert "Flexible(child: Expanded(" not in body
    assert "Expanded(child: Flexible(" not in body


def test_visible_extracted_must_not_emit_empty_shell() -> None:
    planned = {
        "lib/widgets/card_widget.dart": """
class CardWidget extends StatelessWidget {
  const CardWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return const SizedBox.shrink();
  }
}
""",
    }
    with pytest.raises(PlannedDartGraphError, match="visible_extracted_must_not_emit_empty"):
        run_static_contract_gates(planned)


def test_reconcile_final_graph_passes_static_gates_after_prune_consumer() -> None:
    planned = {
        "lib/widgets/section_header_widget.dart": """
import 'package:demo/widgets/cluster_widget.dart';
class SectionHeaderWidget extends StatelessWidget {
  const SectionHeaderWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return Row(children: [const Text('Title'), const ClusterWidget()]);
  }
}
""",
        "lib/generated/demo_layout.dart": """
import 'package:demo/widgets/section_header_widget.dart';
class DemoLayout extends StatelessWidget {
  const DemoLayout({super.key});
  @override
  Widget build(BuildContext context) => const SectionHeaderWidget();
}
""",
    }
    reconciled = reconcile_planned_dart_files(
        planned,
        package_name="demo",
        incremental=True,
    )
    run_static_contract_gates(reconciled)


def test_static_gate_rejects_loose_flex_with_infinite_width() -> None:
    from figma_flutter_agent.errors import PlannedDartGraphError
    from figma_flutter_agent.generator.dart.static_contract_gates import (
        find_loose_flex_infinite_width_violations,
        run_static_contract_gates,
    )

    bad = {
        "lib/widgets/section_header_widget.dart": """
class SectionHeaderWidget extends StatelessWidget {
  const SectionHeaderWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Flexible(fit: FlexFit.loose, flex: 0, child: SizedBox(
        width: double.infinity,
        child: Text('Title'),
      )),
    ]);
  }
}
""",
    }
    violations = find_loose_flex_infinite_width_violations(bad)
    assert violations
    with pytest.raises(PlannedDartGraphError, match="row_flex_child_must_not_force_infinite_width"):
        run_static_contract_gates(bad)


def test_pre_launch_stale_import_scan(tmp_path) -> None:
    widgets = tmp_path / "lib" / "widgets"
    widgets.mkdir(parents=True)
    (widgets / "consumer_widget.dart").write_text(
        """
import 'package:demo/widgets/missing_widget.dart';
class ConsumerWidget extends StatelessWidget {
  const ConsumerWidget({super.key});
  @override
  Widget build(BuildContext context) => const MissingWidget();
}
""",
        encoding="utf-8",
    )
    with pytest.raises(PlannedDartGraphError, match="pre_launch_stale_import_scan"):
        gate_disk_widget_import_closure(tmp_path, package_name="demo")


def test_pre_launch_scoped_to_active_screen_ignores_other_layout_fossils(tmp_path) -> None:
    generated = tmp_path / "lib" / "generated"
    features = tmp_path / "lib" / "features" / "light_theme_06"
    widgets = tmp_path / "lib" / "widgets"
    for folder in (generated, features, widgets):
        folder.mkdir(parents=True, exist_ok=True)
    (generated / "feedback_layout.dart").write_text(
        """
import 'package:inbox/widgets/star_filled_widget.dart';
class FeedbackLayout extends StatelessWidget {
  const FeedbackLayout({super.key});
  @override
  Widget build(BuildContext context) => const StarFilledWidget();
}
""",
        encoding="utf-8",
    )
    (generated / "light_theme_06_layout.dart").write_text(
        """
import 'package:inbox/widgets/footer_widget.dart';
class LightTheme06Layout extends StatelessWidget {
  const LightTheme06Layout({super.key});
  @override
  Widget build(BuildContext context) => const FooterWidget();
}
""",
        encoding="utf-8",
    )
    (widgets / "footer_widget.dart").write_text(
        """
class FooterWidget extends StatelessWidget {
  const FooterWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
        encoding="utf-8",
    )
    (features / "light_theme_06_screen.dart").write_text(
        """
import 'package:inbox/generated/light_theme_06_layout.dart';
class LightTheme06Screen extends StatelessWidget {
  const LightTheme06Screen({super.key});
  @override
  Widget build(BuildContext context) => const LightTheme06Layout();
}
""",
        encoding="utf-8",
    )
    gate_disk_widget_import_closure(
        tmp_path,
        package_name="inbox",
        feature_name="light_theme_06",
    )


def test_widget_ref_implies_def_on_plan_stage() -> None:
    planned = {
        "lib/generated/feedback_layout.dart": """
import 'package:demo/widgets/star_filled_widget.dart';
class FeedbackLayout extends StatelessWidget {
  const FeedbackLayout({super.key});
  @override
  Widget build(BuildContext context) => const StarFilledWidget();
}
""",
    }
    with pytest.raises(PlannedDartGraphError, match="widget_ref_implies_def|stale widget import"):
        run_static_contract_gates(planned)
