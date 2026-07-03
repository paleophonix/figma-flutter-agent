"""Shadow classifier inventory: parser.interaction usage in generator (Program 03 P0-0)."""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ShadowCategory = Literal[
    "fact_reader",
    "layout_policy",
    "kind_decider",
    "emit_archetype_decider",
    "unknown",
]

_RATCHET_CATEGORIES: frozenset[ShadowCategory] = frozenset(
    {
        "kind_decider",
        "emit_archetype_decider",
        "unknown",
    }
)

_INTERACTION_MODULE_PREFIX = "figma_flutter_agent.parser.interaction"

_EMIT_PATH_MARKERS = (
    "/layout/widgets/emit/",
    "/generator/ir/expression.py",
    "/layout/widgets/option_chip.py",
    "/layout/widgets/hero.py",
    "/layout/choice_chip_row.py",
)

_FLEX_POLICY_MARKER = "/layout/flex_policy/"

_FACT_READER_MARKERS = (
    "/geometry/",
    "/ir/validate/guards.py",
    "/background/detection.py",
)


@dataclass(frozen=True, slots=True)
class ShadowClassifierRecord:
    """One classified parser.interaction call site in generator code."""

    path: str
    symbol: str
    imported_symbol: str
    category: ShadowCategory
    semantic_family: str
    rationale: str
    status: str = "active"


@dataclass(frozen=True, slots=True)
class RatchetReport:
    """Baseline-only ratchet comparison result."""

    passed: bool
    new_kind_decider: tuple[ShadowClassifierRecord, ...]
    new_emit_archetype_decider: tuple[ShadowClassifierRecord, ...]
    new_unknown: tuple[ShadowClassifierRecord, ...]
    removed_without_baseline_update: tuple[str, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _generator_root() -> Path:
    return _repo_root() / "src" / "figma_flutter_agent" / "generator"


def _record_key(record: ShadowClassifierRecord) -> str:
    return f"{record.path}|{record.symbol}|{record.imported_symbol}"


def _semantic_family(imported_symbol: str) -> str:
    lowered = imported_symbol.lower()
    if "chip" in lowered:
        return "chip"
    if "checkbox" in lowered or "check" in lowered:
        return "checkbox"
    if "button" in lowered or "cta" in lowered:
        return "button"
    if "nav" in lowered or "back_" in lowered:
        return "nav"
    if "input" in lowered or "field" in lowered or "textarea" in lowered:
        return "input"
    if "payment" in lowered or "selection" in lowered:
        return "selection"
    return "general"


def classify_interaction_usage(
    *,
    rel_path: str,
    host_symbol: str,
    imported_symbol: str,
) -> tuple[ShadowCategory, str]:
    """Classify one interaction import usage in generator code."""
    path_posix = rel_path.replace("\\", "/")
    if any(marker in path_posix for marker in _EMIT_PATH_MARKERS):
        return (
            "emit_archetype_decider",
            "Selects or gates a specialized widget emit archetype",
        )
    if _FLEX_POLICY_MARKER in path_posix:
        return ("layout_policy", "Flex/layout policy predicate for row/column routing")
    if any(marker in path_posix for marker in _FACT_READER_MARKERS):
        return ("fact_reader", "Reads geometry or style facts without emit archetype selection")
    if imported_symbol.startswith("layout_fact_"):
        return ("layout_policy", "Layout fact predicate outside emit dispatch")
    if imported_symbol.startswith(("looks_like_", "is_tag_", "row_hosts_", "row_is_")):
        if "/normalize.py" in path_posix or "/reconcilers" in path_posix:
            return ("layout_policy", "Reconcile-time layout structural predicate")
        return ("emit_archetype_decider", "Interaction predicate used for emit branching")
    if imported_symbol.startswith(("find_", "extract_", "capture_", "collect_")):
        return ("fact_reader", "Reads or extracts Figma facts for downstream use")
    return ("unknown", "Unclassified interaction usage pending inventory review")


class _InteractionCallVisitor(ast.NodeVisitor):
    """Collect interaction symbol calls per enclosing function."""

    def __init__(self, *, rel_path: str, imported_names: dict[str, str]) -> None:
        self._rel_path = rel_path
        self._imported_names = imported_names
        self._current_symbol = "<module>"
        self.records: list[ShadowClassifierRecord] = []
        self._seen: set[tuple[str, str, str]] = set()

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

    def visit_Call(self, node: ast.Call) -> None:
        imported_symbol: str | None = None
        if isinstance(node.func, ast.Name):
            imported_symbol = self._imported_names.get(node.func.id)
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            alias = node.func.value.id
            if alias in self._imported_names:
                imported_symbol = f"{self._imported_names[alias]}.{node.func.attr}"
        if imported_symbol is not None:
            category, rationale = classify_interaction_usage(
                rel_path=self._rel_path,
                host_symbol=self._current_symbol,
                imported_symbol=imported_symbol,
            )
            key = (self._rel_path, self._current_symbol, imported_symbol)
            if key not in self._seen:
                self._seen.add(key)
                self.records.append(
                    ShadowClassifierRecord(
                        path=self._rel_path,
                        symbol=self._current_symbol,
                        imported_symbol=imported_symbol,
                        category=category,
                        semantic_family=_semantic_family(imported_symbol),
                        rationale=rationale,
                    ),
                )
        self.generic_visit(node)


def _collect_imported_names(tree: ast.Module) -> dict[str, str]:
    """Map local alias to fully-qualified imported interaction symbol."""
    names: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            if not node.module.startswith(_INTERACTION_MODULE_PREFIX):
                continue
            suffix = node.module.removeprefix(_INTERACTION_MODULE_PREFIX).lstrip(".")
            for alias in node.names:
                local = alias.asname or alias.name
                if suffix:
                    names[local] = f"{suffix}.{alias.name}".removeprefix(".")
                else:
                    names[local] = alias.name
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_INTERACTION_MODULE_PREFIX):
                    local = alias.asname or alias.name.split(".")[-1]
                    names[local] = alias.name
    return names


def scan_generator_interaction_usage(
    *,
    generator_root: Path | None = None,
) -> list[ShadowClassifierRecord]:
    """Scan generator tree for parser.interaction import call sites."""
    root = generator_root or _generator_root()
    records: list[ShadowClassifierRecord] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(_repo_root() / "src").as_posix()
        rel = f"src/{rel}"
        source = path.read_text(encoding="utf-8")
        if _INTERACTION_MODULE_PREFIX not in source:
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        imported = _collect_imported_names(tree)
        if not imported:
            continue
        visitor = _InteractionCallVisitor(rel_path=rel, imported_names=imported)
        visitor.visit(tree)
        records.extend(visitor.records)
    records.sort(key=lambda item: (_record_key(item), item.category))
    return records


def records_to_json(records: list[ShadowClassifierRecord]) -> str:
    """Serialize inventory deterministically."""
    payload = [asdict(record) for record in records]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def records_from_json(text: str) -> list[ShadowClassifierRecord]:
    """Deserialize inventory JSON."""
    raw = json.loads(text)
    return [
        ShadowClassifierRecord(
            path=item["path"],
            symbol=item["symbol"],
            imported_symbol=item["imported_symbol"],
            category=item["category"],
            semantic_family=item["semantic_family"],
            rationale=item["rationale"],
            status=item.get("status", "active"),
        )
        for item in raw
    ]


def render_inventory_markdown(records: list[ShadowClassifierRecord]) -> str:
    """Generate human-readable inventory report."""
    lines = [
        "# Shadow classifier inventory",
        "",
        "Generated from `docs/refactor/generated/shadow-classifier-inventory.json`.",
        "CI parses JSON only; this file is for review.",
        "",
        "| Path | Host | Imported | Category | Family |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            f"| `{record.path}` | `{record.symbol}` | `{record.imported_symbol}` | "
            f"{record.category} | {record.semantic_family} |"
        )
    counts: dict[str, int] = {}
    for record in records:
        counts[record.category] = counts.get(record.category, 0) + 1
    lines.extend(["", "## Counts", ""])
    for category in sorted(counts):
        lines.append(f"- **{category}**: {counts[category]}")
    lines.append("")
    return "\n".join(lines)


def compare_ratchet(
    *,
    baseline: list[ShadowClassifierRecord],
    current: list[ShadowClassifierRecord],
) -> RatchetReport:
    """Baseline-only ratchet: block new deciders/unknown and silent removals."""
    baseline_map = {_record_key(record): record for record in baseline}
    current_map = {_record_key(record): record for record in current}
    new_kind: list[ShadowClassifierRecord] = []
    new_emit: list[ShadowClassifierRecord] = []
    new_unknown: list[ShadowClassifierRecord] = []
    for key, record in current_map.items():
        if key in baseline_map:
            continue
        if record.category == "kind_decider":
            new_kind.append(record)
        elif record.category == "emit_archetype_decider":
            new_emit.append(record)
        elif record.category == "unknown":
            new_unknown.append(record)
    removed = tuple(sorted(set(baseline_map) - set(current_map)))
    passed = not new_kind and not new_emit and not new_unknown and not removed
    return RatchetReport(
        passed=passed,
        new_kind_decider=tuple(new_kind),
        new_emit_archetype_decider=tuple(new_emit),
        new_unknown=tuple(new_unknown),
        removed_without_baseline_update=removed,
    )


def write_inventory_artifacts(
    *,
    json_path: Path,
    markdown_path: Path,
    records: list[ShadowClassifierRecord] | None = None,
) -> list[ShadowClassifierRecord]:
    """Write canonical JSON and derived markdown inventory."""
    items = records if records is not None else scan_generator_interaction_usage()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(records_to_json(items), encoding="utf-8")
    markdown_path.write_text(render_inventory_markdown(items), encoding="utf-8")
    return items
