"""SemanticEvidence F1 domain contract tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from figma_flutter_agent.generator.ir.passes.provenance_models import (
    SemanticEvidence,
    SemanticEvidenceAllowedEffect,
    SemanticEvidenceLocaleScope,
    SemanticEvidencePolicy,
    SemanticEvidenceProvenance,
    SemanticEvidenceSource,
)


def _provenance(source_field: str = "text") -> SemanticEvidenceProvenance:
    return SemanticEvidenceProvenance(
        nodeId="node:1",
        rule="mock_rule",
        inputValues={"raw": "Password"},
        sourceField=source_field,
    )


def test_text_hint_creates_candidate_evidence() -> None:
    evidence = SemanticEvidence(
        source=SemanticEvidenceSource.TEXT_HINT,
        confidence=0.92,
        provenance=_provenance("text"),
        localeScope=SemanticEvidenceLocaleScope.LOCALE_DEPENDENT,
        allowedEffect=SemanticEvidenceAllowedEffect.CANDIDATE,
    )

    assert evidence.source == SemanticEvidenceSource.TEXT_HINT
    assert evidence.allowed_effect == SemanticEvidenceAllowedEffect.CANDIDATE
    assert evidence.to_payload()["allowedEffect"] == "candidate"


def test_name_hint_creates_candidate_evidence() -> None:
    evidence = SemanticEvidence(
        source=SemanticEvidenceSource.NAME_HINT,
        confidence=0.8,
        provenance=_provenance("name"),
        localeScope=SemanticEvidenceLocaleScope.LOCALE_DEPENDENT,
        allowedEffect=SemanticEvidenceAllowedEffect.CANDIDATE,
    )

    assert evidence.source == SemanticEvidenceSource.NAME_HINT
    assert evidence.allowed_effect == SemanticEvidenceAllowedEffect.CANDIDATE


@pytest.mark.parametrize(
    "source",
    [SemanticEvidenceSource.TEXT_HINT, SemanticEvidenceSource.NAME_HINT],
)
def test_text_and_name_hints_cannot_be_gated_emit(
    source: SemanticEvidenceSource,
) -> None:
    with pytest.raises(ValidationError, match="cannot exceed candidate"):
        SemanticEvidence(
            source=source,
            confidence=1.0,
            provenance=_provenance(source.value.removesuffix("_hint")),
            localeScope=SemanticEvidenceLocaleScope.LOCALE_DEPENDENT,
            allowedEffect=SemanticEvidenceAllowedEffect.GATED_EMIT,
        )


def test_geometry_evidence_can_be_gated_emit() -> None:
    evidence = SemanticEvidence(
        source=SemanticEvidenceSource.GEOMETRY,
        confidence=0.95,
        provenance=_provenance("bounds"),
        localeScope=SemanticEvidenceLocaleScope.GLOBAL,
        allowedEffect=SemanticEvidenceAllowedEffect.GATED_EMIT,
    )

    assert evidence.allowed_effect == SemanticEvidenceAllowedEffect.GATED_EMIT


def test_component_property_can_be_gated_source() -> None:
    evidence = SemanticEvidence(
        source=SemanticEvidenceSource.COMPONENT_PROPERTY,
        confidence=0.99,
        provenance=_provenance("component_property"),
        localeScope=SemanticEvidenceLocaleScope.GLOBAL,
        allowedEffect=SemanticEvidenceAllowedEffect.GATED_EMIT,
    )

    assert evidence.source == SemanticEvidenceSource.COMPONENT_PROPERTY
    assert evidence.to_payload()["provenance"]["sourceField"] == "component_property"


def test_candidate_evidence_has_no_production_effect() -> None:
    evidence = SemanticEvidence(
        source=SemanticEvidenceSource.TEXT_HINT,
        confidence=0.92,
        provenance=_provenance("text"),
        localeScope=SemanticEvidenceLocaleScope.LOCALE_DEPENDENT,
        allowedEffect=SemanticEvidenceAllowedEffect.CANDIDATE,
    )

    assert not SemanticEvidencePolicy(allow_gated_emit=True).allows_production_effect(evidence)


def test_gated_emit_requires_explicit_policy() -> None:
    evidence = SemanticEvidence(
        source=SemanticEvidenceSource.GEOMETRY,
        confidence=0.95,
        provenance=_provenance("bounds"),
        localeScope=SemanticEvidenceLocaleScope.GLOBAL,
        allowedEffect=SemanticEvidenceAllowedEffect.GATED_EMIT,
    )

    assert not SemanticEvidencePolicy().allows_production_effect(evidence)
    assert SemanticEvidencePolicy(allow_gated_emit=True).allows_production_effect(evidence)


ROOT = Path(__file__).resolve().parents[1]


def test_semantic_evidence_models_do_not_import_runtime_recorders() -> None:
    module_path = (
        ROOT
        / "src"
        / "figma_flutter_agent"
        / "generator"
        / "ir"
        / "passes"
        / "provenance_models.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "figma_flutter_agent.debug.provenance" not in imports
    assert "figma_flutter_agent.generator.ir.passes.protocol" not in imports
