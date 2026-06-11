"""Batch semantic classification against fixture corpora."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.generator.ir.tree import default_screen_ir, index_clean_tree
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.schemas import CleanDesignTreeNode, WidgetIrKind


@dataclass(frozen=True)
class CorpusCase:
    """One semantics fixture case."""

    path: Path
    expected_kind: WidgetIrKind | None
    forbidden_kinds: frozenset[WidgetIrKind]
    target_figma_id: str | None


@dataclass
class CorpusResult:
    """Outcome for a single corpus case."""

    path: Path
    passed: bool
    message: str
    classified_kind: str | None


def load_clean_tree_fixture(path: Path) -> CleanDesignTreeNode:
    """Load a clean-tree JSON fixture."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "clean_tree" in payload:
        payload = payload["clean_tree"]
    if "root" in payload:
        payload = payload["root"]
    return CleanDesignTreeNode.model_validate(payload)


def parse_manifest_entry(path: Path, data: dict[str, object]) -> CorpusCase:
    """Parse one manifest row."""
    expected_raw = data.get("expected_kind")
    expected = WidgetIrKind(str(expected_raw)) if expected_raw else None
    forbidden_raw = data.get("forbidden_kinds") or []
    forbidden = frozenset(WidgetIrKind(str(item)) for item in forbidden_raw)
    target = data.get("target_figma_id")
    return CorpusCase(
        path=path,
        expected_kind=expected,
        forbidden_kinds=forbidden,
        target_figma_id=str(target) if target else None,
    )


def run_case(
    case: CorpusCase,
    *,
    confidence_threshold: float = 0.8,
    grey_zone_min: float = 0.5,
) -> CorpusResult:
    """Classify one fixture and evaluate expectations."""
    clean_tree = load_clean_tree_fixture(case.path)
    screen_ir = default_screen_ir(clean_tree)
    updated_ir, report = classify_screen_ir(
        screen_ir,
        clean_tree,
        confidence_threshold=confidence_threshold,
        grey_zone_min=grey_zone_min,
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
    if case.expected_kind is None and kind_enum in SEMANTIC_IR_KINDS and case.forbidden_kinds:
        return CorpusResult(
            path=case.path,
            passed=False,
            message=f"unexpected semantic kind {classified_kind}",
            classified_kind=classified_kind,
        )
    _ = report
    return CorpusResult(
        path=case.path,
        passed=True,
        message="ok",
        classified_kind=classified_kind,
    )


def _find_kind(node, figma_id: str) -> str | None:
    if node.figma_id == figma_id:
        return node.kind.value
    for child in node.children:
        found = _find_kind(child, figma_id)
        if found is not None:
            return found
    return None
