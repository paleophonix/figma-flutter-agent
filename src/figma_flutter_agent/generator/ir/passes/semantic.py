"""Semantic classification IR pass."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.protocol import Pass, PassContext, pass_from_callable
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir


def _run_classify_screen_ir(ctx: PassContext) -> PassContext:
    from figma_flutter_agent.config import load_settings

    semantics = load_settings().agent.semantics
    if not semantics.enabled:
        return ctx

    updated_ir, report = classify_screen_ir(
        ctx.screen_ir,
        ctx.clean_tree,
        confidence_threshold=semantics.confidence_threshold,
        grey_zone_min=semantics.grey_zone_min,
        authoritative_classifier=semantics.authoritative_classifier,
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
        import json
        from pathlib import Path

        from figma_flutter_agent.debug.paths import FIGMA_DEBUG_DIR

        report_path = Path(FIGMA_DEBUG_DIR) / "classification_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2),
            encoding="utf-8",
        )
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
