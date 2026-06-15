"""Diff-triada: cleanTree → normalize → emit for audit corpus entries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.audit.corpus import AUDIT_CORPUS, AuditCorpusEntry
from figma_flutter_agent.generator.emit_fidelity_audit import audit_emit_contracts
from figma_flutter_agent.generator.geometry.invariants.validate import validate_geometry_invariants
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass(slots=True)
class DiffTriadaRecord:
    """Audit snapshot for one corpus layout."""

    pattern_class: str
    feature_name: str
    layout_path: str
    node_count_pre: int
    node_count_post: int
    geometry_soft_violations: list[str]
    emit_fidelity_violations: list[str]
    emit_snippet: str
    layout_dart_path: str


def _count_nodes(node: CleanDesignTreeNode) -> int:
    total = 1
    for child in node.children:
        total += _count_nodes(child)
    return total


def _load_tree(entry: AuditCorpusEntry) -> CleanDesignTreeNode:
    raw = json.loads(entry.layout_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "cleanTree" in raw:
        return CleanDesignTreeNode.model_validate(raw["cleanTree"])
    return CleanDesignTreeNode.model_validate(raw)


def run_diff_triada_for_entry(entry: AuditCorpusEntry) -> DiffTriadaRecord:
    """Normalize and emit one corpus entry; collect invariant and fidelity gaps."""
    tree = _load_tree(entry)
    pre_count = _count_nodes(tree)
    normalized = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        strict_geometry_invariants=False,
    )
    post_count = _count_nodes(normalized)
    violations = validate_geometry_invariants(
        normalized,
        require_layout_slots=True,
        strict_invariants=False,
    )
    soft_codes = sorted(
        {f"{item.code}@{item.node_id}" for item in violations if item.severity == "soft"}
    )
    planned = render_layout_file(
        normalized,
        feature_name=entry.feature_name,
        uses_svg=False,
        use_geometry_planner=True,
    )
    layout_key = f"lib/generated/{entry.feature_name}_layout.dart"
    layout_source = planned.get(layout_key, "")
    fidelity = audit_emit_contracts(normalized, layout_source)
    fidelity_codes = sorted({item.code for item in fidelity})
    snippet = layout_source.replace("\n", " ")[:500]
    return DiffTriadaRecord(
        pattern_class=entry.pattern_class,
        feature_name=entry.feature_name,
        layout_path=str(entry.layout_path),
        node_count_pre=pre_count,
        node_count_post=post_count,
        geometry_soft_violations=soft_codes,
        emit_fidelity_violations=fidelity_codes,
        emit_snippet=snippet,
        layout_dart_path=layout_key,
    )


def run_diff_triada(
    *,
    output_dir: Path | None = None,
    entries: tuple[AuditCorpusEntry, ...] | None = None,
) -> list[DiffTriadaRecord]:
    """Run diff-triada across the audit corpus and optionally write JSON artifacts."""
    from loguru import logger

    corpus = entries or AUDIT_CORPUS
    records: list[DiffTriadaRecord] = []
    for entry in corpus:
        if not entry.layout_path.is_file():
            logger.warning("Skipping missing audit layout: {}", entry.layout_path)
            continue
        try:
            records.append(run_diff_triada_for_entry(entry))
        except Exception:
            logger.exception("Diff-triada skipped for {}", entry.layout_path)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        payload: list[dict[str, Any]] = [asdict(item) for item in records]
        (output_dir / "diff_triada.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return records
