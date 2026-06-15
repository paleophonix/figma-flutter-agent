"""FID-26 emit contract criterion for spec §23 signoff gates."""

from __future__ import annotations

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.emit_fidelity_audit import audit_emit_contracts
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.validation.spec23.models import Spec23CriterionResult


def _criterion_emit_fidelity_contracts(
    tree: CleanDesignTreeNode,
    layout_sources: str,
    *,
    settings: Settings,
    strict: bool,
) -> Spec23CriterionResult:
    """Fail signoff when emit contract gaps are detected (FID-26)."""
    validation = settings.agent.validation
    if not validation.strict_emit_contracts:
        return Spec23CriterionResult(
            name="emit_fidelity_contracts",
            passed=True,
            detail="report-only",
        )
    if not strict or not layout_sources.strip():
        return Spec23CriterionResult(
            name="emit_fidelity_contracts",
            passed=True,
            detail="skipped",
        )
    violations = audit_emit_contracts(
        tree,
        layout_sources,
        viewport_height=tree.sizing.height,
    )
    if not violations:
        return Spec23CriterionResult(
            name="emit_fidelity_contracts",
            passed=True,
            detail="clean",
        )
    codes = ", ".join(sorted({item.code for item in violations}))
    return Spec23CriterionResult(
        name="emit_fidelity_contracts",
        passed=False,
        detail=codes,
    )
