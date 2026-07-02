"""Classify screen IR nodes using staged semantic detectors."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.parser.semantics.arbiter import arbitrate, merge_signals
from figma_flutter_agent.parser.semantics.detectors import DETECTORS
from figma_flutter_agent.parser.semantics.models import (
    Classification,
    DetectorContext,
    TierSignals,
)
from figma_flutter_agent.parser.semantics.prefilter import (
    SEMANTIC_IR_KINDS,
    plausible_kinds,
)
from figma_flutter_agent.parser.semantics.report import (
    ReportNode,
    SemanticClassificationReport,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)
from figma_flutter_agent.schemas.ir_payloads import (
    ChipChoicePayload,
    InputTextFieldPayload,
    KindPayload,
    LlmClassificationHint,
)


@dataclass(frozen=True)
class ClassificationReportEntry:
    """One node outcome from a classification run (legacy corpus shape)."""

    figma_id: str
    kind: str
    confidence: float
    accepted: bool
    evidence: dict[str, object]


@dataclass
class ClassificationReport:
    """Legacy aggregate report wrapper."""

    entries: list[ClassificationReportEntry]
    semantic: SemanticClassificationReport | None = None

    def to_dict(self) -> dict[str, object]:
        if self.semantic is not None:
            return self.semantic.to_dict()
        return {
            "entries": [
                {
                    "figmaId": entry.figma_id,
                    "kind": entry.kind,
                    "confidence": entry.confidence,
                    "accepted": entry.accepted,
                    "evidence": entry.evidence,
                }
                for entry in self.entries
            ],
            "accepted_count": sum(1 for entry in self.entries if entry.accepted),
            "total": len(self.entries),
        }


def _apply_payload_to_ir(
    ir_node: WidgetIrNode, kind: WidgetIrKind, payload: KindPayload
) -> WidgetIrNode:
    updates: dict[str, object] = {"kind": kind, "payload": payload}
    if isinstance(payload, ChipChoicePayload):
        updates["is_selected"] = payload.is_selected
    if isinstance(payload, InputTextFieldPayload):
        updates["hint_text"] = payload.hint_text
        updates["error_text"] = payload.error_text
        updates["is_multiline"] = payload.is_multiline
        updates["max_lines"] = payload.max_lines
    return ir_node.model_copy(update=updates)


def _record_legacy_type_signals(
    report: SemanticClassificationReport,
    *,
    figma_id: str,
    evidence: dict[str, object],
) -> None:
    from figma_flutter_agent.generator.geometry.invariants.type_truth import (
        is_legacy_semantic_type_node,
    )

    if is_legacy_semantic_type_node(figma_id):
        if figma_id not in report.legacy_semantic_type_detected:
            report.legacy_semantic_type_detected.append(figma_id)
        if figma_id not in report.name_signal_used:
            report.name_signal_used.append(figma_id)
    if evidence.get("signalSource") == "legacy_interaction":
        if figma_id not in report.name_signal_used:
            report.name_signal_used.append(figma_id)


def classify_node(
    ir_node: WidgetIrNode,
    clean_node: CleanDesignTreeNode,
    *,
    clean_by_id: dict[str, CleanDesignTreeNode],
    screen_ir: ScreenIr,
    confidence_threshold: float,
    grey_zone_min: float,
    llm_hint: LlmClassificationHint | None = None,
    llm_gray_zone_enabled: bool = False,
    report: SemanticClassificationReport | None = None,
) -> tuple[WidgetIrNode, ClassificationReportEntry]:
    """Classify one IR node against its clean-tree counterpart."""
    effective_hint = llm_hint if llm_gray_zone_enabled else None
    if effective_hint is not None:
        from figma_flutter_agent.generator.ir.validate.root_kind import (
            nav_bottom_bar_kind_contradicts_clean_node,
        )

        if (
            effective_hint.suggested_kind == WidgetIrKind.NAV_BOTTOM_BAR.value
            and nav_bottom_bar_kind_contradicts_clean_node(clean_node)
        ):
            effective_hint = None
    ctx = merge_signals(
        DetectorContext(
            clean_node=clean_node,
            ir_node=ir_node,
            clean_by_id=clean_by_id,
            screen_ir=screen_ir,
            signals=TierSignals(),
            confidence_threshold=confidence_threshold,
            grey_zone_min=grey_zone_min,
            llm_hint=effective_hint,
        )
    )

    candidates: list[Classification] = []
    for kind in plausible_kinds(clean_node):
        detector = DETECTORS.get(kind)
        if detector is None:
            continue
        result = detector.detect(ctx)
        if result is not None:
            candidates.append(result)

    outcome = arbitrate(candidates, ctx)
    merged_evidence = {
        **outcome.evidence,
        **ctx.signals.anatomy_hits,
        **ctx.signals.property_hits,
    }
    if report is not None:
        if outcome.bucket is not None:
            resolved_kind = (
                outcome.kind.value
                if isinstance(outcome.kind, WidgetIrKind)
                else outcome.runner_up_kind
            )
            node = ReportNode(
                figma_id=ir_node.figma_id,
                kind=resolved_kind,
                confidence=outcome.confidence,
                evidence=merged_evidence,
                reject_reason=outcome.reject_reason,
            )
            report.add(outcome.bucket, node)
        _record_legacy_type_signals(
            report,
            figma_id=ir_node.figma_id,
            evidence=merged_evidence,
        )

    kind = outcome.kind
    payload = outcome.payload
    if (
        kind is None
        or not isinstance(kind, WidgetIrKind)
        or kind not in SEMANTIC_IR_KINDS
        or payload is None
    ):
        return ir_node, ClassificationReportEntry(
            figma_id=ir_node.figma_id,
            kind=ir_node.kind.value,
            confidence=0.0,
            accepted=False,
            evidence=merged_evidence,
        )

    updated = _apply_payload_to_ir(ir_node, kind, payload)  # type: ignore[arg-type]
    return updated, ClassificationReportEntry(
        figma_id=ir_node.figma_id,
        kind=kind.value,
        confidence=outcome.confidence,
        accepted=True,
        evidence=merged_evidence,
    )


def classify_screen_ir(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    confidence_threshold: float = 0.8,
    grey_zone_min: float = 0.5,
    authoritative_classifier: bool = True,
    llm_gray_zone_enabled: bool = False,
) -> tuple[ScreenIr, ClassificationReport]:
    """Walk IR and clean tree in parallel, classifying each node."""
    from figma_flutter_agent.generator.ir.tree import index_clean_tree

    clean_by_id = index_clean_tree(clean_tree)
    entries: list[ClassificationReportEntry] = []
    semantic_report = SemanticClassificationReport()

    def walk(ir_node: WidgetIrNode) -> WidgetIrNode:
        clean_node = clean_by_id.get(ir_node.figma_id)
        if clean_node is None:
            children = [walk(child) for child in ir_node.children]
            return ir_node.model_copy(update={"children": children})

        working = ir_node
        hint = working.classification_hint
        if authoritative_classifier and working.kind in SEMANTIC_IR_KINDS:
            from figma_flutter_agent.generator.ir.validate.root_kind import (
                downgrade_nav_bottom_bar_ir_node,
            )

            downgraded = downgrade_nav_bottom_bar_ir_node(working, clean_node)
            if downgraded.kind not in SEMANTIC_IR_KINDS:
                working = downgraded
                hint = None
            else:
                hint = LlmClassificationHint(
                    suggested_kind=working.kind.value,
                    confidence=hint.confidence if hint is not None else grey_zone_min,
                    rationale=hint.rationale if hint is not None else None,
                )
                working = working.model_copy(update={"kind": WidgetIrKind.AUTO})

        classified, entry = classify_node(
            working,
            clean_node,
            clean_by_id=clean_by_id,
            screen_ir=screen_ir,
            confidence_threshold=confidence_threshold,
            grey_zone_min=grey_zone_min,
            llm_hint=hint,
            llm_gray_zone_enabled=llm_gray_zone_enabled,
            report=semantic_report,
        )
        entries.append(entry)
        children = [walk(child) for child in classified.children]
        return classified.model_copy(update={"children": children})

    updated_root = walk(screen_ir.root)
    return screen_ir.model_copy(update={"root": updated_root}), ClassificationReport(
        entries=entries,
        semantic=semantic_report,
    )
