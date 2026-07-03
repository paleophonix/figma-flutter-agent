"""Decorative primitive decision inventory and ratchet (Program 07 P0-0)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

DecorativeDecisionRoute = Literal[
    "collapse_boundary",
    "composite_export",
    "forms_checkmark",
    "navigation_substrate",
    "svg_emit",
    "vector_dispatch",
    "extracted_paint",
    "unknown",
]

_RATCHET_ROUTES: frozenset[DecorativeDecisionRoute] = frozenset({"unknown"})

_SCAN_TARGETS: tuple[tuple[str, DecorativeDecisionRoute, tuple[str, ...]], ...] = (
    (
        "src/figma_flutter_agent/parser/boundaries/collapse.py",
        "collapse_boundary",
        ("children = []", "flatten_figma_node_ids", "render_boundary"),
    ),
    (
        "src/figma_flutter_agent/assets/composite_icons.py",
        "composite_export",
        ("composite", "svg", "export"),
    ),
    (
        "src/figma_flutter_agent/parser/interaction/forms.py",
        "forms_checkmark",
        ("checkmark", "checkbox", "decorative"),
    ),
    (
        "src/figma_flutter_agent/generator/layout/navigation",
        "navigation_substrate",
        ("bottom_nav", "nav_bar", "tab_bar"),
    ),
    (
        "src/figma_flutter_agent/generator/layout/widgets/svg.py",
        "svg_emit",
        ("SvgPicture", "vector", "render_boundary"),
    ),
    (
        "src/figma_flutter_agent/generator/layout/widgets/emit/dispatch.py",
        "vector_dispatch",
        ("VECTOR", "svg", "render_boundary"),
    ),
    (
        "src/figma_flutter_agent/generator/ir/extracted_paint.py",
        "extracted_paint",
        ("icon_badge", "extracted_paint", "plate"),
    ),
)

INVENTORY_JSON_REL = (
    "docs/refactor/26-06-06-compiler-refactor/generated/decorative-decision-inventory.json"
)
RATCHET_BASELINE_JSON_REL = (
    "docs/refactor/26-06-06-compiler-refactor/generated/"
    "decorative-decision-inventory-ratchet-baseline.json"
)


@dataclass(frozen=True, slots=True)
class DecorativeDecisionRecord:
    """One classified decorative routing decision site."""

    path: str
    symbol: str
    route: DecorativeDecisionRoute
    marker: str
    line: int
    rationale: str
    status: str = "active"


@dataclass(frozen=True, slots=True)
class DecorativeRatchetReport:
    """Baseline-only ratchet for unknown decorative routes."""

    passed: bool
    new_unknown: tuple[DecorativeDecisionRecord, ...]
    removed_without_baseline_update: tuple[str, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _record_key(record: DecorativeDecisionRecord) -> str:
    return f"{record.path}|{record.symbol}|{record.route}|{record.marker}|{record.line}"


def _ratchet_key(record: DecorativeDecisionRecord) -> str:
    return f"{record.path}|{record.symbol}|{record.route}|{record.marker}"


def _scan_file(
    path: Path,
    *,
    rel_path: str,
    route: DecorativeDecisionRoute,
    markers: tuple[str, ...],
) -> list[DecorativeDecisionRecord]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[DecorativeDecisionRecord] = []
    seen: set[str] = set()
    symbol = "<module>"
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("def "):
            symbol = stripped[4:].split("(")[0].strip()
        for marker in markers:
            if marker.lower() not in line.lower():
                continue
            record = DecorativeDecisionRecord(
                path=rel_path,
                symbol=symbol,
                route=route,
                marker=marker,
                line=lineno,
                rationale=f"Decorative route {route} marker {marker!r}",
            )
            key = _ratchet_key(record)
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
    return records


def scan_decorative_decisions(*, repo_root: Path | None = None) -> list[DecorativeDecisionRecord]:
    """Scan compiler paths for decorative primitive routing decisions."""
    root = repo_root or _repo_root()
    records: list[DecorativeDecisionRecord] = []
    for rel_path, route, markers in _SCAN_TARGETS:
        target = root / rel_path
        if target.is_dir():
            for py_file in sorted(target.rglob("*.py")):
                file_rel = py_file.relative_to(root).as_posix()
                records.extend(
                    _scan_file(py_file, rel_path=file_rel, route=route, markers=markers)
                )
        else:
            records.extend(
                _scan_file(target, rel_path=rel_path, route=route, markers=markers)
            )
    records.sort(key=_record_key)
    return records


def records_to_json(records: list[DecorativeDecisionRecord]) -> str:
    payload = [asdict(record) for record in records]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def records_from_json(text: str) -> list[DecorativeDecisionRecord]:
    raw = json.loads(text)
    return [
        DecorativeDecisionRecord(
            path=item["path"],
            symbol=item["symbol"],
            route=item["route"],
            marker=item["marker"],
            line=item["line"],
            rationale=item["rationale"],
            status=item.get("status", "active"),
        )
        for item in raw
    ]


def compare_decorative_ratchet(
    *,
    baseline: list[DecorativeDecisionRecord],
    current: list[DecorativeDecisionRecord],
) -> DecorativeRatchetReport:
    baseline_map = {_ratchet_key(record): record for record in baseline}
    current_map = {_ratchet_key(record): record for record in current}
    new_unknown: list[DecorativeDecisionRecord] = []
    for key, record in current_map.items():
        if key in baseline_map:
            continue
        if record.route in _RATCHET_ROUTES:
            new_unknown.append(record)
    removed = tuple(sorted(set(baseline_map) - set(current_map)))
    return DecorativeRatchetReport(
        passed=not new_unknown,
        new_unknown=tuple(new_unknown),
        removed_without_baseline_update=removed,
    )


def load_ratchet_baseline_records() -> tuple[list[DecorativeDecisionRecord], str]:
    """Load frozen decorative decision ratchet baseline."""
    frozen = _repo_root() / RATCHET_BASELINE_JSON_REL
    if frozen.is_file():
        return (
            records_from_json(frozen.read_text(encoding="utf-8")),
            f"frozen:{RATCHET_BASELINE_JSON_REL}",
        )
    inventory = _repo_root() / INVENTORY_JSON_REL
    if inventory.is_file():
        return (
            records_from_json(inventory.read_text(encoding="utf-8")),
            f"frozen:{INVENTORY_JSON_REL}",
        )
    raise FileNotFoundError(f"decorative decision ratchet baseline not found ({frozen})")


def run_decorative_decision_ratchet_gate() -> DecorativeRatchetReport:
    """Compare live scan against approved ratchet baseline."""
    baseline, _source = load_ratchet_baseline_records()
    current = scan_decorative_decisions()
    return compare_decorative_ratchet(baseline=baseline, current=current)


def write_inventory_artifacts(
    *,
    json_path: Path,
    records: list[DecorativeDecisionRecord] | None = None,
) -> list[DecorativeDecisionRecord]:
    items = records if records is not None else scan_decorative_decisions()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(records_to_json(items), encoding="utf-8")
    return items


def write_ratchet_baseline(
    *,
    path: Path | None = None,
    records: list[DecorativeDecisionRecord] | None = None,
) -> list[DecorativeDecisionRecord]:
    items = records if records is not None else scan_decorative_decisions()
    target = path or (_repo_root() / RATCHET_BASELINE_JSON_REL)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(records_to_json(items), encoding="utf-8")
    return items
