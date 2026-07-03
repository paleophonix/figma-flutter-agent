"""Conservation law registry tests (Program 02 P0-1)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants import conservation
from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
    run_conservation_laws,
)
from figma_flutter_agent.generator.geometry.invariants.models import VIOLATION_SEVERITY
from figma_flutter_agent.generator.geometry.invariants.registry import (
    CONSERVATION_LAWS,
    ConservationLaw,
    ConservationLawContext,
    ConservationStage,
    LawOwner,
    all_violation_codes,
    execute_conservation_laws,
    law_by_id,
    laws_for_stage,
)
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_at_least_ten_conservation_laws_registered() -> None:
    assert len(CONSERVATION_LAWS) >= 10


def test_each_law_has_unique_law_id() -> None:
    ids = [law.law_id for law in CONSERVATION_LAWS]
    assert len(ids) == len(set(ids))


def test_violation_codes_exist_in_severity_map_or_have_check_fn() -> None:
    for law in CONSERVATION_LAWS:
        if not law.violation_codes:
            continue
        for code in law.violation_codes:
            assert code in VIOLATION_SEVERITY or code in {
                "inv_geometry_truth",
                "inv_flex_child_stack_placement",
                "inv_ir_kind",
            }


def test_check_symbols_resolve_to_callable() -> None:
    for law in CONSERVATION_LAWS:
        if law.owner.module.endswith("conservation.py"):
            assert hasattr(conservation, law.check_symbol)
        assert callable(law.check_fn)


def test_cp2_and_post_classify_stages_populated() -> None:
    cp2 = laws_for_stage("CP2")
    post = laws_for_stage("post_classify")
    assert any(law.law_id == "LAW-CONSERVE-MULTISET" for law in cp2)
    assert any(law.law_id == "LAW-CP2-CLASSIFY-SCOPE" for law in post)


def test_classify_scope_law_lookup() -> None:
    law = law_by_id("LAW-CP2-CLASSIFY-SCOPE")
    assert law is not None
    assert isinstance(law, ConservationLaw)
    assert law.violation_codes == ("inv_classification_scope",)
    assert law.check_symbol == "check_ir_classification_scope"


def test_all_violation_codes_nonempty_for_conservation_checks() -> None:
    codes = all_violation_codes()
    assert "inv_node_multiset" in codes
    assert "inv_classification_scope" in codes


def test_runner_invokes_registered_synthetic_law(monkeypatch) -> None:
    calls: list[ConservationStage] = []

    def _synthetic_check(_ctx: ConservationLawContext) -> list:
        calls.append("CP2")
        return []

    synthetic = ConservationLaw(
        law_id="LAW-TEST-SYNTHETIC",
        violation_codes=("inv_node_multiset",),
        check_symbol="synthetic",
        check_fn=_synthetic_check,
        stage="CP2",
        severity="block",
        owner=LawOwner(module="tests/test_conservation_registry.py", symbol="synthetic"),
        description="synthetic test law",
    )
    monkeypatch.setattr(
        "figma_flutter_agent.generator.geometry.invariants.registry.laws_for_stage",
        lambda stage: (synthetic,) if stage == "CP2" else (),
    )

    clean = CleanDesignTreeNode(id="root", name="root", type=NodeType.COLUMN)
    screen_ir = default_screen_ir(clean)
    run_conservation_laws(
        "CP2",
        baseline_clean=clean,
        current_clean=clean,
        baseline_ir=screen_ir,
        current_ir=screen_ir,
    )
    assert calls == ["CP2"]


def test_execute_conservation_laws_loops_registry() -> None:
    clean = CleanDesignTreeNode(id="root", name="root", type=NodeType.COLUMN)
    screen_ir = default_screen_ir(clean)
    ctx = ConservationLawContext(
        baseline_clean=clean,
        current_clean=clean,
        baseline_ir=screen_ir,
        current_ir=screen_ir,
    )
    violations = execute_conservation_laws("CP2", ctx)
    assert violations == []
