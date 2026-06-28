"""Regression tests for cluster delegate graph acyclicity."""

from figma_flutter_agent.generator.cluster_variants import resolve_cluster_delegate_class
from figma_flutter_agent.generator.planned.reconcile.delegate_repair import (
    repair_mutual_delegate_widget_cycles,
    repair_self_referential_widget_builds,
)
from figma_flutter_agent.generator.widget_extractor import _component_family_already_extracted
from figma_flutter_agent.schemas import CleanDesignTreeNode, ComponentVariant, NodeType, Sizing


def test_resolve_cluster_delegate_skips_same_component_family_aliases() -> None:
    node = CleanDesignTreeNode(
        id="btn",
        name="Button",
        type=NodeType.BUTTON,
        cluster_id="component_3016_10287_d2e87d01",
        component_ref="3016:10287",
        variant=ComponentVariant(component_id="3016:10287", component_name="Button"),
        sizing=Sizing(width=74.0, height=36.0),
    )
    cluster_classes = {
        "component_3016_10287": "Cluster10287Widget",
        "component_3016_10287_d2e87d01": "Clusterd2e87d01Widget",
        "component_3016_10135_d2e87d01": "Clusterd2e87d01Widget",
    }
    delegate = resolve_cluster_delegate_class(
        node,
        cluster_classes,
        skip_cluster_id="component_3016_10287_d2e87d01",
    )
    assert delegate is None


def test_component_family_not_duplicated_when_fingerprint_cluster_exists() -> None:
    existing = {"component_3016_10287_d2e87d01"}
    assert _component_family_already_extracted("3016:10287", existing)


def test_repair_mutual_delegate_widget_cycles_breaks_two_node_cycle() -> None:
    planned = {
        "lib/widgets/cluster10287_widget.dart": """
class Cluster10287Widget extends StatelessWidget {
  const Cluster10287Widget({super.key});
  @override
  Widget build(BuildContext context) {
    return SizedBox(width: 74.0, height: 36.0, child: const Clusterd2e87d01Widget());
  }
}
""",
        "lib/widgets/clusterd2e87d01_widget.dart": """
class Clusterd2e87d01Widget extends StatelessWidget {
  const Clusterd2e87d01Widget({super.key});
  @override
  Widget build(BuildContext context) {
    return SizedBox(width: 74.0, height: 36.0, child: const Cluster10287Widget());
  }
}
""",
    }
    updated = repair_self_referential_widget_builds(planned)
    a = updated["lib/widgets/cluster10287_widget.dart"]
    b = updated["lib/widgets/clusterd2e87d01_widget.dart"]
    assert not ("Clusterd2e87d01Widget()" in a and "Cluster10287Widget()" in b)


def test_repair_mutual_delegate_widget_cycles_direct_api() -> None:
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
    updated = repair_mutual_delegate_widget_cycles(planned)
    assert "const BWidget()" not in updated["lib/widgets/a_widget.dart"]
    assert "const AWidget()" not in updated["lib/widgets/b_widget.dart"]
