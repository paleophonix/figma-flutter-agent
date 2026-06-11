"""W1 semantics corpus precision/recall aggregation (EPIC 5.W1)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from figma_flutter_agent.parser.semantics.corpus import (
    CorpusCase,
    CorpusResult,
    load_fixture_payload,
    parse_corpus_case,
    run_case,
)
from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.schemas import WidgetIrKind


def _default_manifest_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tests" / "fixtures" / "layouts" / "semantics" / "manifest.yaml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("semantics corpus manifest.yaml not found")


_DEFAULT_MANIFEST = _default_manifest_path()

W1_KINDS: frozenset[WidgetIrKind] = frozenset(
    {
        WidgetIrKind.BUTTON_FILLED,
        WidgetIrKind.BUTTON_OUTLINED,
        WidgetIrKind.BUTTON_TEXT,
        WidgetIrKind.INPUT_TEXT_FIELD,
        WidgetIrKind.CHIP_CHOICE,
        WidgetIrKind.CONTAINER_CARD,
        WidgetIrKind.CONTAINER_LIST_TILE,
        WidgetIrKind.TECHNICAL_DIVIDER,
    }
)

DEFAULT_GATES = {
    "overall_precision_min": 0.95,
    "per_kind_precision_min": 0.90,
    "recall_min": 0.80,
    "blocker_negative_false_positives_max": 0,
}


@dataclass(frozen=True)
class W1Manifest:
    """Parsed W1 section of the semantics corpus manifest."""

    kinds: tuple[WidgetIrKind, ...]
    positive_paths: tuple[Path, ...]
    blocker_negative_paths: tuple[Path, ...]
    fixture_root: Path


@dataclass
class KindMetrics:
    """Per-kind classification counts."""

    kind: str
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float | None:
        denom = self.true_positive + self.false_positive
        if denom == 0:
            return None
        return self.true_positive / denom

    @property
    def recall(self) -> float | None:
        denom = self.true_positive + self.false_negative
        if denom == 0:
            return None
        return self.true_positive / denom


@dataclass
class W1GateReport:
    """Aggregated W1 corpus gate results."""

    overall_precision: float | None
    overall_recall: float | None
    per_kind: dict[str, KindMetrics]
    blocker_negative_false_positives: int
    backlog_false_negatives: list[dict[str, str]] = field(default_factory=list)
    failed_cases: list[dict[str, str]] = field(default_factory=list)
    gates: dict[str, float | int] = field(default_factory=lambda: dict(DEFAULT_GATES))
    passed: bool = False

    def to_json_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["per_kind"] = {
            key: {
                **asdict(metrics),
                "precision": metrics.precision,
                "recall": metrics.recall,
            }
            for key, metrics in self.per_kind.items()
        }
        return payload


def load_w1_manifest(path: Path | None = None) -> W1Manifest:
    """Load the W1 corpus manifest section.

    Args:
        path: Optional manifest path; defaults to repo semantics manifest.

    Returns:
        Parsed ``W1Manifest``.

    Raises:
        FileNotFoundError: When the manifest file is missing.
        KeyError: When the ``w1`` section is absent.
    """
    manifest_path = path or _DEFAULT_MANIFEST
    raw = YAML(typ="safe").load(manifest_path.read_text(encoding="utf-8"))
    section = raw["w1"]
    fixture_root = manifest_path.parent
    kinds = tuple(WidgetIrKind(str(item)) for item in section["kinds"])
    positives = tuple(fixture_root / str(item) for item in section["positive_cases"])
    blockers = tuple(fixture_root / str(item) for item in section["blocker_negatives"])
    return W1Manifest(
        kinds=kinds,
        positive_paths=positives,
        blocker_negative_paths=blockers,
        fixture_root=fixture_root,
    )


def _load_case(path: Path) -> CorpusCase:
    return parse_corpus_case(path, load_fixture_payload(path))


def _kind_metrics_map(kinds: tuple[WidgetIrKind, ...]) -> dict[str, KindMetrics]:
    return {kind.value: KindMetrics(kind=kind.value) for kind in kinds}


def _classified_w1_kind(result: CorpusResult) -> WidgetIrKind | None:
    if result.classified_kind is None:
        return None
    kind = WidgetIrKind(result.classified_kind)
    if kind not in W1_KINDS:
        return None
    return kind


def evaluate_w1_corpus(
    manifest: W1Manifest | None = None,
    *,
    gates: dict[str, float | int] | None = None,
) -> W1GateReport:
    """Run W1 positive and blocker-negative corpora and aggregate gate metrics.

    Args:
        manifest: Optional pre-loaded manifest.
        gates: Optional threshold overrides.

    Returns:
        ``W1GateReport`` with pass/fail and per-kind metrics.
    """
    loaded = manifest or load_w1_manifest()
    thresholds = {**DEFAULT_GATES, **(gates or {})}
    per_kind = _kind_metrics_map(loaded.kinds)

    total_tp = 0
    total_fp = 0
    total_fn = 0
    backlog: list[dict[str, str]] = []
    failed_cases: list[dict[str, str]] = []

    for path in loaded.positive_paths:
        case = _load_case(path)
        result = run_case(case)
        if not result.passed:
            failed_cases.append(
                {
                    "path": path.as_posix(),
                    "message": result.message,
                    "classified_kind": result.classified_kind or "",
                }
            )
        expected = case.expected_kind
        classified = _classified_w1_kind(result)
        if expected is None:
            continue
        if classified == expected:
            per_kind[expected.value].true_positive += 1
            total_tp += 1
        else:
            per_kind[expected.value].false_negative += 1
            total_fn += 1
            backlog.append(
                {
                    "path": path.as_posix(),
                    "expected_kind": expected.value,
                    "classified_kind": result.classified_kind or "",
                    "message": result.message,
                }
            )
            if classified is not None:
                per_kind[classified.value].false_positive += 1
                total_fp += 1

    blocker_fp = 0
    for path in loaded.blocker_negative_paths:
        case = _load_case(path)
        result = run_case(case)
        if not result.passed:
            blocker_fp += 1
            failed_cases.append(
                {
                    "path": path.as_posix(),
                    "message": result.message,
                    "classified_kind": result.classified_kind or "",
                }
            )
            classified = _classified_w1_kind(result)
            if classified is not None:
                per_kind[classified.value].false_positive += 1
                total_fp += 1

    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else None
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else None

    report = W1GateReport(
        overall_precision=overall_precision,
        overall_recall=overall_recall,
        per_kind=per_kind,
        blocker_negative_false_positives=blocker_fp,
        backlog_false_negatives=backlog,
        failed_cases=failed_cases,
        gates=thresholds,
    )
    report.passed = _gate_passed(report, thresholds)
    return report


def _gate_passed(report: W1GateReport, thresholds: dict[str, float | int]) -> bool:
    if report.blocker_negative_false_positives > int(
        thresholds["blocker_negative_false_positives_max"]
    ):
        return False
    precision_min = float(thresholds["overall_precision_min"])
    recall_min = float(thresholds["recall_min"])
    per_kind_min = float(thresholds["per_kind_precision_min"])
    if report.overall_precision is None or report.overall_precision < precision_min:
        return False
    if report.overall_recall is None or report.overall_recall < recall_min:
        return False
    for metrics in report.per_kind.values():
        if metrics.true_positive == 0 and metrics.false_negative == 0:
            continue
        if metrics.precision is None or metrics.precision < per_kind_min:
            return False
    return True


def write_gate_report(report: W1GateReport, path: Path) -> None:
    """Persist a gate report as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_json_dict(), indent=2), encoding="utf-8")


def is_w1_semantic_kind(kind: WidgetIrKind) -> bool:
    """Return True when ``kind`` is part of the W1 target set."""
    return kind in W1_KINDS


def is_semantic_ir_kind_value(value: str | None) -> bool:
    """Return True when a classified kind string is a registered semantic IR kind."""
    if value is None:
        return False
    try:
        return WidgetIrKind(value) in SEMANTIC_IR_KINDS
    except ValueError:
        return False


__all__ = [
    "DEFAULT_GATES",
    "W1GateReport",
    "W1_KINDS",
    "W1Manifest",
    "KindMetrics",
    "evaluate_w1_corpus",
    "is_semantic_ir_kind_value",
    "is_w1_semantic_kind",
    "load_w1_manifest",
    "write_gate_report",
]
