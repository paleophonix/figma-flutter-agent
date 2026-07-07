"""Conservation invariant validators and checkpoint tests."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
    activate_conservation_session,
    clear_conservation_session,
    run_cp0_parse_dedup,
    run_cp2_ir_passes,
    set_parse_style_baseline,
)
from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_graph_sync,
    check_node_multiset_preserved,
    check_stack_paint_order_preserved,
    check_style_truth,
    conservation_node_multiset,
)
from figma_flutter_agent.generator.geometry.invariants.models import VIOLATION_SEVERITY
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.parser.dedup.prune import (
    prune_duplicated_cluster_subtrees,
    prune_generation_layout_tree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


def _icon_row(count: int) -> CleanDesignTreeNode:
    cluster_id = "cluster:icon"
    return CleanDesignTreeNode(
        id="row",
        name="Row",
        type=NodeType.ROW,
        children=[
            CleanDesignTreeNode(
                id=f"icon:{index}",
                name=f"Icon {index}",
                type=NodeType.STACK,
                cluster_id=cluster_id,
                children=[
                    CleanDesignTreeNode(
                        id=f"vec:{index}",
                        name="Vector",
                        type=NodeType.VECTOR,
                    ),
                ],
            )
            for index in range(count)
        ],
    )


def test_conservation_codes_are_hard() -> None:
    for code in (
        "inv_node_multiset",
        "inv_stack_paint_order",
        "inv_style_truth",
        "inv_graph_sync",
    ):
        assert VIOLATION_SEVERITY[code] == "hard"


def test_cp0_parse_dedup_preserves_multiset_for_cluster_prune() -> None:
    root = _icon_row(3)
    run_cp0_parse_dedup(root, prune_fn=lambda: prune_duplicated_cluster_subtrees(root))
    assert conservation_node_multiset(root).get("vec:1") == 1
    assert all(child.children == [] for child in root.children[1:])


def test_cp0_parse_dedup_fails_when_node_dropped() -> None:
    root = _icon_row(2)

    def bad_prune() -> None:
        root.children = root.children[:1]

    with pytest.raises(GenerationError, match="inv_node_multiset"):
        run_cp0_parse_dedup(root, prune_fn=bad_prune)


def test_multiset_count_mismatch_reports_count_detail() -> None:
    baseline = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="vec-1",
                name="Vector",
                type=NodeType.VECTOR,
            ),
        ],
    )
    doubled = deep_copy_clean_tree(baseline)
    doubled.children[0].flatten_figma_node_ids = ["vec-1"]
    violations = check_node_multiset_preserved(baseline, doubled)
    assert len(violations) == 1
    assert violations[0].node_id == "vec-1"
    assert "count_mismatch=['vec-1: 1 -> 2']" in violations[0].detail


def test_multiset_count_mismatch_culprit_preserves_figma_instance_ids() -> None:
    baseline = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="I4408:44896;1154:7849",
                name="Stepper",
                type=NodeType.STACK,
            ),
        ],
    )
    doubled = deep_copy_clean_tree(baseline)
    doubled.children[0].flatten_figma_node_ids = ["I4408:44896;1154:7849"]
    violations = check_node_multiset_preserved(baseline, doubled)
    assert len(violations) == 1
    assert violations[0].node_id == "I4408:44896;1154:7849"


def test_stack_paint_order_violation_detected() -> None:
    clean = CleanDesignTreeNode(
        id="stack:root",
        name="Row",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(id="a", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="b", name="B", type=NodeType.TEXT, text="B"),
        ],
    )
    reordered = deep_copy_clean_tree(clean)
    reordered.children = list(reversed(reordered.children))
    violations = check_stack_paint_order_preserved(clean, reordered)
    assert violations
    assert violations[0].code == "inv_stack_paint_order"


def test_graph_sync_detects_child_mismatch() -> None:
    clean = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        children=[CleanDesignTreeNode(id="a", name="A", type=NodeType.TEXT, text="A")],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.COLUMN,
            children=[WidgetIrNode(figma_id="missing", kind=WidgetIrKind.AUTO)],
        ),
    )
    violations = check_graph_sync(screen_ir, clean)
    assert any(item.code == "inv_graph_sync" for item in violations)


def test_style_truth_allows_provenance_policy() -> None:
    session = activate_conservation_session()
    tree = CleanDesignTreeNode(
        id="text:1",
        name="Label",
        type=NodeType.TEXT,
        text="Hi",
        style={"fontSize": 9.0, "textColor": "#000000"},
    )
    set_parse_style_baseline(tree)
    bumped = tree.model_copy(deep=True)
    bumped.style.font_size = 12.0
    violations = check_style_truth(
        session.style_baseline,
        bumped,
        allowed_mutations={("text:1", "font_size"): "accessibility.auto_fix"},
    )
    assert not violations
    clear_conservation_session()


def test_cp2_ir_passes_runs_after_apply_ir_layout_passes() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing={"width": 360.0, "height": 1200.0},
        children=[
            CleanDesignTreeNode(
                id="block",
                name="Block",
                type=NodeType.TEXT,
                text="Body",
                sizing={"width": 300.0, "height": 20.0},
            ),
        ],
    )
    screen_ir = default_screen_ir(tree)
    baseline_clean = deep_copy_clean_tree(tree)
    baseline_ir = screen_ir.model_copy(deep=True)
    updated_ir, updated_clean = apply_ir_layout_passes(
        screen_ir,
        tree,
        macro_height_threshold_px=900,
        validate_cp2=True,
    )
    run_cp2_ir_passes(baseline_clean, baseline_ir, updated_clean, updated_ir)


def test_prune_generation_layout_tree_with_checkpoint_none_for_unit_fixtures() -> None:
    root = _icon_row(2)
    before = conservation_node_multiset(root)
    prune_generation_layout_tree(root, checkpoint=None)
    assert conservation_node_multiset(root) == before


def test_cp1_normalize_allows_weekday_chip_row_synthesis() -> None:
    """Law: normalize_reconcile_must_register_sanctioned_synthetic_clean_nodes."""
    import json
    from pathlib import Path

    from figma_flutter_agent.generator.geometry.invariants.checkpoints import run_cp1_normalize
    from figma_flutter_agent.generator.normalize import reconcile_layout_tree
    from figma_flutter_agent.parser.layout.reconcilers_ui import (
        is_weekday_chip_row_wrapper_id,
        weekday_chip_row_synthesized_node_ids,
    )

    processed_path = (
        Path(__file__).resolve().parents[1] / ".debug/screen/limbo/reminders/processed.json"
    )
    if not processed_path.is_file():
        pytest.skip("reminders processed dump not available")
    tree = CleanDesignTreeNode.model_validate(
        json.loads(processed_path.read_text(encoding="utf-8"))["cleanTree"],
    )
    result = run_cp1_normalize(
        tree,
        transform_fn=lambda node: reconcile_layout_tree(node, archetype_reconcile=False),
    )
    synthesized = weekday_chip_row_synthesized_node_ids(result)
    assert synthesized
    assert all(is_weekday_chip_row_wrapper_id(node_id) for node_id in synthesized)


def test_normalize_clean_tree_passes_for_reminders_weekday_row() -> None:
    """CP1 normalize must not abort when core weekday chip row reconcile runs."""
    import json
    from pathlib import Path

    from figma_flutter_agent.generator.normalize import normalize_clean_tree

    processed_path = (
        Path(__file__).resolve().parents[1] / ".debug/screen/limbo/reminders/processed.json"
    )
    if not processed_path.is_file():
        pytest.skip("reminders processed dump not available")
    tree = CleanDesignTreeNode.model_validate(
        json.loads(processed_path.read_text(encoding="utf-8"))["cleanTree"],
    )
    normalize_clean_tree(tree, archetype_reconcile=False, apply_render_safety=False)


def test_cp2_blocks_unpermitted_omit_ids() -> None:
    """Multiset omit ids require typed OmissionReason permits."""
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        run_conservation_laws,
    )

    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="child", name="Child", type=NodeType.TEXT, text="x"),
        ],
    )
    baseline = deep_copy_clean_tree(root)
    current = deep_copy_clean_tree(root)
    current.children = []
    screen_ir = default_screen_ir(root)
    screen_ir = screen_ir.model_copy(update={"omit_figma_ids": ["child"]})
    violations = run_conservation_laws(
        "CP2",
        baseline_clean=baseline,
        current_clean=current,
        baseline_ir=screen_ir,
        current_ir=screen_ir,
        omit_ids=frozenset({"child"}),
    )
    assert any(v.code == "inv_omission_unpermitted" for v in violations)
