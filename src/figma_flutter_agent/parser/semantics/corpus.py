"""Batch semantic classification against fixture corpora."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.generator.geometry.invariants.type_truth import (
    is_legacy_semantic_type_node,
)
from figma_flutter_agent.generator.ir.tree import default_screen_ir, index_clean_tree
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr, WidgetIrKind, WidgetIrNode


@dataclass(frozen=True)
class CorpusCase:
    """One semantics fixture case."""

    path: Path
    expected_kind: WidgetIrKind | None
    forbidden_kinds: frozenset[WidgetIrKind]
    target_figma_id: str | None
    target_figma_ids: frozenset[str] = frozenset()
    require_zero_semantic: bool = False


@dataclass
class CorpusResult:
    """Outcome for a single corpus case."""

    path: Path
    passed: bool
    message: str
    classified_kind: str | None


def load_fixture_payload(path: Path) -> dict[str, object]:
    """Load raw JSON object from a semantics corpus fixture."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_clean_tree_fixture(path: Path) -> CleanDesignTreeNode:
    """Load a clean-tree JSON fixture."""
    payload = load_fixture_payload(path)
    if "clean_tree" in payload:
        payload = payload["clean_tree"]
    if "root" in payload:
        payload = payload["root"]
    return CleanDesignTreeNode.model_validate(payload)


def load_tree_fixture(path: Path) -> CleanDesignTreeNode:
    """Load a clean-tree fixture or parse ``figma_root`` through the real parser."""
    payload = load_fixture_payload(path)
    figma_root = payload.get("figma_root")
    if figma_root is not None:
        from figma_flutter_agent.parser.tree import build_clean_tree

        tree, _, _, _ = build_clean_tree(figma_root)
        return tree
    return load_clean_tree_fixture(path)


def parse_corpus_case(path: Path, data: dict[str, object]) -> CorpusCase:
    """Parse fixture metadata into a ``CorpusCase``."""
    expected_raw = data.get("expected_kind")
    expected = WidgetIrKind(str(expected_raw)) if expected_raw else None
    forbidden_raw = data.get("forbidden_kinds") or []
    forbidden = frozenset(WidgetIrKind(str(item)) for item in forbidden_raw)
    target = data.get("target_figma_id")
    targets_raw = data.get("target_figma_ids") or []
    target_ids = frozenset(str(item) for item in targets_raw)
    require_zero = bool(data.get("require_zero_semantic"))
    return CorpusCase(
        path=path,
        expected_kind=expected,
        forbidden_kinds=forbidden,
        target_figma_id=str(target) if target else None,
        target_figma_ids=target_ids,
        require_zero_semantic=require_zero,
    )


def classify_fixture_tree(
    case: CorpusCase,
    *,
    confidence_threshold: float = 0.8,
    grey_zone_min: float = 0.5,
) -> tuple[ScreenIr, object]:
    """Classify a fixture and return updated screen IR plus the classification report."""
    clean_tree = load_tree_fixture(case.path)
    screen_ir = default_screen_ir(clean_tree)
    updated_ir, report = classify_screen_ir(
        screen_ir,
        clean_tree,
        confidence_threshold=confidence_threshold,
        grey_zone_min=grey_zone_min,
    )
    return updated_ir, report


def run_case(
    case: CorpusCase,
    *,
    confidence_threshold: float = 0.8,
    grey_zone_min: float = 0.5,
    updated_ir: ScreenIr | None = None,
    report: object | None = None,
) -> CorpusResult:
    """Classify one fixture and evaluate expectations."""
    clean_tree = load_tree_fixture(case.path)
    if updated_ir is None or report is None:
        updated_ir, report = classify_fixture_tree(
            case,
            confidence_threshold=confidence_threshold,
            grey_zone_min=grey_zone_min,
        )

    if case.require_zero_semantic and case.target_figma_ids:
        return _evaluate_zero_semantic_targets(
            case,
            updated_ir=updated_ir,
            report=report,
        )

    indexed = index_clean_tree(clean_tree)

    if case.target_figma_id:
        target_id = case.target_figma_id
    elif len(indexed) == 1:
        target_id = next(iter(indexed))
    else:
        target_id = clean_tree.id

    classified_kind = _find_kind(updated_ir.root, target_id)
    if classified_kind is None:
        return CorpusResult(
            path=case.path,
            passed=False,
            message=f"target node {target_id!r} not found in IR",
            classified_kind=None,
        )

    kind_enum = WidgetIrKind(classified_kind)
    if case.forbidden_kinds and kind_enum in case.forbidden_kinds:
        return CorpusResult(
            path=case.path,
            passed=False,
            message=f"forbidden kind {classified_kind} on trap fixture",
            classified_kind=classified_kind,
        )
    if case.expected_kind is not None and kind_enum != case.expected_kind:
        return CorpusResult(
            path=case.path,
            passed=False,
            message=f"expected {case.expected_kind.value}, got {classified_kind}",
            classified_kind=classified_kind,
        )
    _ = report
    return CorpusResult(
        path=case.path,
        passed=True,
        message="ok",
        classified_kind=classified_kind,
    )


def _evaluate_zero_semantic_targets(
    case: CorpusCase,
    *,
    updated_ir,
    report,
) -> CorpusResult:
    """Pass when every target is legacy-marked and receives no semantic kind."""
    accepted_ids: set[str] = set()
    if report.semantic is not None:
        accepted_ids.update(node.figma_id for node in report.semantic.accepted)

    for target_id in sorted(case.target_figma_ids):
        if not is_legacy_semantic_type_node(target_id):
            return CorpusResult(
                path=case.path,
                passed=False,
                message=f"target {target_id!r} is not legacy-marked after parse",
                classified_kind=None,
            )
        kind_value = _find_kind(updated_ir.root, target_id)
        if kind_value is None:
            return CorpusResult(
                path=case.path,
                passed=False,
                message=f"target node {target_id!r} not found in IR",
                classified_kind=None,
            )
        kind_enum = WidgetIrKind(kind_value)
        if kind_enum in SEMANTIC_IR_KINDS:
            return CorpusResult(
                path=case.path,
                passed=False,
                message=f"semantic kind {kind_value} on legacy name-hint node {target_id!r}",
                classified_kind=kind_value,
            )
        if report.semantic is not None and target_id in accepted_ids:
            return CorpusResult(
                path=case.path,
                passed=False,
                message=f"legacy name-hint node {target_id!r} appears in classification report",
                classified_kind=kind_value,
            )
    return CorpusResult(
        path=case.path,
        passed=True,
        message="ok",
        classified_kind=None,
    )


def _find_kind(node, figma_id: str) -> str | None:
    if node.figma_id == figma_id:
        return node.kind.value
    for child in node.children:
        found = _find_kind(child, figma_id)
        if found is not None:
            return found
    return None


def iter_semantic_ir_nodes(
    node: WidgetIrNode,
    *,
    kinds: frozenset[WidgetIrKind],
) -> list[tuple[str, WidgetIrKind]]:
    """Collect ``(figma_id, kind)`` pairs for nodes whose kind is in ``kinds``."""
    hits: list[tuple[str, WidgetIrKind]] = []
    if node.kind in kinds:
        hits.append((node.figma_id, node.kind))
    for child in node.children:
        hits.extend(iter_semantic_ir_nodes(child, kinds=kinds))
    return hits


def allowed_semantic_target_ids(case: CorpusCase) -> frozenset[str]:
    """Return figma ids that may carry a W1 semantic kind in full-tree audit."""
    if case.require_zero_semantic:
        return frozenset()
    if case.expected_kind is not None and case.target_figma_id:
        return frozenset({case.target_figma_id})
    return frozenset()
