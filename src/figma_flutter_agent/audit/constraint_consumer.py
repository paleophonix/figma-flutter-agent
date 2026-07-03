"""Raw constraint string consumer inventory and ratchet (Program 06 P0-0a)."""

from __future__ import annotations

import ast
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ConstraintConsumerCategory = Literal[
    "parser_fact",
    "reconcile_transform",
    "planner_slot",
    "emit_positioned",
    "ir_guard",
    "schema_type",
    "unknown",
]

_RATCHET_CATEGORIES: frozenset[ConstraintConsumerCategory] = frozenset(
    {
        "planner_slot",
        "emit_positioned",
        "ir_guard",
        "unknown",
    }
)

_RAW_CONSTRAINT_TOKENS: frozenset[str] = frozenset(
    {
        "LEFT",
        "RIGHT",
        "TOP",
        "BOTTOM",
        "CENTER",
        "LEFT_RIGHT",
        "TOP_BOTTOM",
        "SCALE",
    }
)

_SCAN_ROOTS = (
    "src/figma_flutter_agent/parser/layout",
    "src/figma_flutter_agent/generator/geometry",
    "src/figma_flutter_agent/generator/layout",
    "src/figma_flutter_agent/generator/ir/validate",
    "src/figma_flutter_agent/schemas",
)

INVENTORY_JSON_REL = (
    "docs/refactor/26-06-06-compiler-refactor/generated/constraint-consumers.json"
)
RATCHET_BASELINE_JSON_REL = (
    "docs/refactor/26-06-06-compiler-refactor/generated/constraint-consumers-ratchet-baseline.json"
)


@dataclass(frozen=True, slots=True)
class ConstraintConsumerRecord:
    """One classified raw constraint string read in compiler code."""

    path: str
    symbol: str
    token: str
    line: int
    category: ConstraintConsumerCategory
    axis: str
    rationale: str
    status: str = "active"


@dataclass(frozen=True, slots=True)
class ConstraintRatchetReport:
    """Baseline-only ratchet comparison for direct raw constraint consumers."""

    passed: bool
    new_direct_consumer: tuple[ConstraintConsumerRecord, ...]
    removed_without_baseline_update: tuple[str, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _record_key(record: ConstraintConsumerRecord) -> str:
    return f"{record.path}|{record.symbol}|{record.token}|{record.line}"


def classify_constraint_consumer(
    *,
    rel_path: str,
    host_symbol: str,
    token: str,
) -> tuple[ConstraintConsumerCategory, str, str]:
    """Classify one raw constraint token usage."""
    path_posix = rel_path.replace("\\", "/")
    axis = "both"
    if token in {"TOP", "BOTTOM", "TOP_BOTTOM"}:
        axis = "vertical"
    elif token in {"LEFT", "RIGHT", "LEFT_RIGHT", "CENTER", "SCALE"}:
        axis = "horizontal"
    if "/schemas/" in path_posix or path_posix.endswith("types.py"):
        return ("schema_type", axis, "Schema or enum definition for constraint vocabulary")
    if "/parser/layout/placement" in path_posix or "/parser/layout/sizing" in path_posix:
        return ("parser_fact", axis, "Parser placement fact read or normalize")
    if "/reconcilers" in path_posix or "reconcile_" in path_posix:
        return ("reconcile_transform", axis, "Reconcile pass mutates placement constraints")
    if "/generator/geometry/slots" in path_posix:
        return ("planner_slot", axis, "Planner slot derivation from placement")
    if "/ir/validate/graph" in path_posix:
        return ("ir_guard", axis, "IR graph render-safety guard on placement")
    if "/emit/" in path_posix or "/positioned" in path_posix or "/widgets/text" in path_posix:
        return ("emit_positioned", axis, "Emit-time positioned or flex constraint branch")
    if "/layout/responsive" in path_posix:
        return ("planner_slot", axis, "Responsive layout constraint routing")
    return ("unknown", axis, "Unclassified direct raw constraint read pending review")


class _ConstraintStringVisitor(ast.NodeVisitor):
    """Collect string constant constraint token reads per enclosing function."""

    def __init__(self, *, rel_path: str) -> None:
        self._rel_path = rel_path
        self._current_symbol = "<module>"
        self.records: list[ConstraintConsumerRecord] = []
        self._seen: set[tuple[str, str, str, int]] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        previous = self._current_symbol
        self._current_symbol = node.name
        self.generic_visit(node)
        self._current_symbol = previous

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        previous = self._current_symbol
        self._current_symbol = node.name
        self.generic_visit(node)
        self._current_symbol = previous

    def _maybe_record(self, token: str, line: int) -> None:
        if token not in _RAW_CONSTRAINT_TOKENS:
            return
        key = (self._rel_path, self._current_symbol, token, line)
        if key in self._seen:
            return
        self._seen.add(key)
        category, axis, rationale = classify_constraint_consumer(
            rel_path=self._rel_path,
            host_symbol=self._current_symbol,
            token=token,
        )
        self.records.append(
            ConstraintConsumerRecord(
                path=self._rel_path,
                symbol=self._current_symbol,
                token=token,
                line=line,
                category=category,
                axis=axis,
                rationale=rationale,
            ),
        )

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self._maybe_record(node.value, node.lineno)
        self.generic_visit(node)

    def visit_Set(self, node: ast.Set) -> None:
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                self._maybe_record(elt.value, elt.lineno)
        self.generic_visit(node)

    def visit_List(self, node: ast.List) -> None:
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                self._maybe_record(elt.value, elt.lineno)
        self.generic_visit(node)


def scan_constraint_consumers(*, repo_root: Path | None = None) -> list[ConstraintConsumerRecord]:
    """Scan compiler paths for direct raw constraint string reads."""
    root = repo_root or _repo_root()
    records: list[ConstraintConsumerRecord] = []
    for scan_root in _SCAN_ROOTS:
        base = root / scan_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            source = path.read_text(encoding="utf-8")
            if not any(token in source for token in _RAW_CONSTRAINT_TOKENS):
                continue
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError:
                continue
            visitor = _ConstraintStringVisitor(rel_path=rel)
            visitor.visit(tree)
            records.extend(visitor.records)
    records.sort(key=lambda item: (_record_key(item), item.category))
    return records


def records_to_json(records: list[ConstraintConsumerRecord]) -> str:
    """Serialize inventory deterministically."""
    payload = [asdict(record) for record in records]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def records_from_json(text: str) -> list[ConstraintConsumerRecord]:
    """Deserialize inventory JSON."""
    raw = json.loads(text)
    return [
        ConstraintConsumerRecord(
            path=item["path"],
            symbol=item["symbol"],
            token=item["token"],
            line=item["line"],
            category=item["category"],
            axis=item["axis"],
            rationale=item["rationale"],
            status=item.get("status", "active"),
        )
        for item in raw
    ]


def compare_constraint_ratchet(
    *,
    baseline: list[ConstraintConsumerRecord],
    current: list[ConstraintConsumerRecord],
) -> ConstraintRatchetReport:
    """Block new direct consumers in ratchet categories; allow shrink."""
    baseline_map = {_record_key(record): record for record in baseline}
    current_map = {_record_key(record): record for record in current}
    new_direct: list[ConstraintConsumerRecord] = []
    for key, record in current_map.items():
        if key in baseline_map:
            continue
        if record.category in _RATCHET_CATEGORIES:
            new_direct.append(record)
    removed = tuple(sorted(set(baseline_map) - set(current_map)))
    passed = not new_direct
    return ConstraintRatchetReport(
        passed=passed,
        new_direct_consumer=tuple(new_direct),
        removed_without_baseline_update=removed,
    )


def _git_run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )


def _git_show_text(ref: str, rel_path: str) -> str | None:
    result = _git_run(["show", f"{ref}:{rel_path}"])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout


def resolve_ratchet_baseline_git_ref() -> str | None:
    """Resolve git ref for ratchet baseline."""
    explicit = os.environ.get("FIGMA_CONSTRAINT_RATCHET_REF", "").strip()
    if explicit:
        verify = _git_run(["rev-parse", "--verify", explicit])
        if verify.returncode == 0:
            return verify.stdout.strip()
    merge_base = _git_run(["merge-base", "HEAD", "main"])
    if merge_base.returncode == 0 and merge_base.stdout.strip():
        return merge_base.stdout.strip()
    parent = _git_run(["rev-parse", "--verify", "HEAD~1"])
    if parent.returncode == 0:
        return parent.stdout.strip()
    return None


def load_ratchet_baseline_records() -> tuple[list[ConstraintConsumerRecord], str]:
    """Load approved ratchet baseline from git ref or frozen JSON."""
    ref = resolve_ratchet_baseline_git_ref()
    if ref:
        for rel_path in (RATCHET_BASELINE_JSON_REL, INVENTORY_JSON_REL):
            text = _git_show_text(ref, rel_path)
            if text is not None:
                return records_from_json(text), f"git:{ref}:{rel_path}"
    frozen = _repo_root() / RATCHET_BASELINE_JSON_REL
    if frozen.is_file():
        return (
            records_from_json(frozen.read_text(encoding="utf-8")),
            f"frozen:{RATCHET_BASELINE_JSON_REL}",
        )
    raise FileNotFoundError(
        "constraint consumer ratchet baseline not found "
        f"(git ref={ref!r}, frozen={frozen})",
    )


def run_constraint_consumer_ratchet_gate() -> ConstraintRatchetReport:
    """Compare live scan against approved ratchet baseline."""
    baseline, _source = load_ratchet_baseline_records()
    current = scan_constraint_consumers()
    return compare_constraint_ratchet(baseline=baseline, current=current)


def write_inventory_artifacts(
    *,
    json_path: Path,
    records: list[ConstraintConsumerRecord] | None = None,
) -> list[ConstraintConsumerRecord]:
    """Write canonical JSON inventory."""
    items = records if records is not None else scan_constraint_consumers()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(records_to_json(items), encoding="utf-8")
    return items


def write_ratchet_baseline(
    *,
    path: Path | None = None,
    records: list[ConstraintConsumerRecord] | None = None,
) -> list[ConstraintConsumerRecord]:
    """Persist frozen ratchet baseline after conscious remediation shrink."""
    items = records if records is not None else scan_constraint_consumers()
    target = path or (_repo_root() / RATCHET_BASELINE_JSON_REL)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(records_to_json(items), encoding="utf-8")
    return items
