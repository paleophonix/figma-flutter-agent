"""Semantic classification IR pass."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.protocol import (
    Pass,
    PassContext,
    pass_from_callable,
)
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir


def _run_classify_screen_ir(ctx: PassContext) -> PassContext:
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.debug.semantics import write_classification_report

    semantics = load_settings().agent.semantics
    if not semantics.enabled:
        return ctx

    updated_ir, report = classify_screen_ir(
        ctx.screen_ir,
        ctx.clean_tree,
        confidence_threshold=semantics.confidence_threshold,
        grey_zone_min=semantics.grey_zone_min,
        authoritative_classifier=semantics.authoritative_classifier,
        llm_gray_zone_enabled=semantics.llm_gray_zone_annotations,
    )
    if ctx.provenance is not None:
        for entry in report.entries:
            if not entry.accepted:
                continue
            ctx.provenance.record_decision(
                node_id=entry.figma_id,
                kind=entry.kind,
                confidence=entry.confidence,
                evidence=entry.evidence,
            )
        ctx.provenance.note_checkpoint("CP2_semantic")
    if report.semantic is not None:
        feature = ctx.provenance.feature_name if ctx.provenance is not None else "screen"
        project_dir = ctx.provenance.project_dir if ctx.provenance is not None else None
        write_classification_report(feature, report.semantic, project_dir=project_dir)
    return ctx.with_trees(updated_ir, ctx.clean_tree)


classify_screen_ir_pass = pass_from_callable(
    "classify_screen_ir",
    _run_classify_screen_ir,
    mutates=frozenset({"screen_ir.kind", "screen_ir.payload", "screen_ir.classification_hint"}),
    preserves=frozenset(
        {
            "node_multiset",
            "stack_paint_order",
            "graph_sync",
            "style",
            "geometry",
        }
    ),
)

SEMANTIC_PASSES: tuple[Pass, ...] = (classify_screen_ir_pass,)
