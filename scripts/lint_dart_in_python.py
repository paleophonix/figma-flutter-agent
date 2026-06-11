#!/usr/bin/env python3
"""Lint for Dart widget string literals outside templates (EPIC 3.4 / 4.5)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR_ROOT = ROOT / "src" / "figma_flutter_agent" / "generator"
SCAN_ROOT = GENERATOR_ROOT
BLOCKING_ROOTS = (GENERATOR_ROOT / "ir",)
COUNT_BASELINE_PATH = ROOT / "tests" / "fixtures" / "lint" / "dart_sniff_baseline.json"
FINGERPRINT_BASELINE_PATH = ROOT / "linters" / "emitter_baseline.txt"
DEFAULT_OWNER_EPIC = "E4.5"

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bContainer\("), "dart_widget_literal"),
    (re.compile(r"\bSizedBox\("), "dart_widget_literal"),
    (re.compile(r"\bPositioned\("), "dart_widget_literal"),
    (re.compile(r"\bElevatedButton\("), "dart_widget_literal"),
    (re.compile(r"\bChoiceChip\("), "dart_widget_literal"),
    (re.compile(r"\bTextField\("), "dart_widget_literal"),
)

ALLOWLIST_PREFIXES = (
    SCAN_ROOT / "templates",
)

DEBT_ZONE_PREFIXES = (
    SCAN_ROOT / "layout",
    SCAN_ROOT / "dart",
    SCAN_ROOT / "checks",
    SCAN_ROOT / "ambient_background",
    SCAN_ROOT / "figma_anchor",
    SCAN_ROOT / "geometry",
    SCAN_ROOT / "planned",
    SCAN_ROOT / "subtree",
    SCAN_ROOT / "theme",
    SCAN_ROOT / "renderer.py",
)

LAYOUT_WIDGETS_ROOT = SCAN_ROOT / "layout" / "widgets"
CONTEXT_LINES = 3


@dataclass(frozen=True)
class ViolationFingerprint:
    """Stable identity for one legacy-zone Dart literal occurrence."""

    path: str
    snippet_hash: str
    category: str
    owner_epic: str

    @property
    def key(self) -> str:
        return f"{self.path}|{self.snippet_hash}|{self.category}"

    def format_line(self) -> str:
        return f"{self.path} | {self.snippet_hash} | {self.category} | {self.owner_epic}"


def _is_allowlisted(path: Path) -> bool:
    resolved = path.resolve()
    return any(
        resolved.is_relative_to(prefix.resolve())
        for prefix in (*ALLOWLIST_PREFIXES, *DEBT_ZONE_PREFIXES)
    )


def _is_blocking_path(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved.is_relative_to(root.resolve()) for root in BLOCKING_ROOTS)


def _is_legacy_debt_path(path: Path) -> bool:
    resolved = path.resolve()
    return resolved.is_relative_to(LAYOUT_WIDGETS_ROOT.resolve())


def _normalize_snippet(text: str, match_start: int) -> str:
    lines = text.splitlines()
    line_no = text.count("\n", 0, match_start)
    lo = max(0, line_no - CONTEXT_LINES)
    hi = min(len(lines), line_no + CONTEXT_LINES + 1)
    chunk = "\n".join(line.strip() for line in lines[lo:hi])
    return re.sub(r"\s+", " ", chunk).strip()


def _snippet_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]


def _collect_file_fingerprints(
    path: Path,
    *,
    owner_epic: str,
) -> list[ViolationFingerprint]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT).as_posix()
    fingerprints: list[ViolationFingerprint] = []
    for pattern, category in PATTERNS:
        for match in pattern.finditer(text):
            normalized = _normalize_snippet(text, match.start())
            fingerprints.append(
                ViolationFingerprint(
                    path=rel,
                    snippet_hash=_snippet_hash(normalized),
                    category=category,
                    owner_epic=owner_epic,
                ),
            )
    return fingerprints


def collect_blocking_violations() -> list[ViolationFingerprint]:
    """Collect Dart sniff violations in clean emit zones (``generator/ir``)."""
    violations: list[ViolationFingerprint] = []
    for blocking_root in BLOCKING_ROOTS:
        for path in sorted(blocking_root.rglob("*.py")):
            if _is_allowlisted(path):
                continue
            violations.extend(_collect_file_fingerprints(path, owner_epic="blocking"))
    return violations


def collect_legacy_fingerprints() -> list[ViolationFingerprint]:
    """Collect fingerprinted violations under ``layout/widgets``."""
    fingerprints: list[ViolationFingerprint] = []
    for path in sorted(LAYOUT_WIDGETS_ROOT.rglob("*.py")):
        fingerprints.extend(_collect_file_fingerprints(path, owner_epic=DEFAULT_OWNER_EPIC))
    return fingerprints


def count_layout_widget_sniffs() -> int:
    """Count sniff patterns under layout/widgets (burn-down metric only)."""
    return len(collect_legacy_fingerprints())


def load_fingerprint_baseline(path: Path = FINGERPRINT_BASELINE_PATH) -> dict[str, ViolationFingerprint]:
    """Load allowlisted legacy fingerprints from the baseline file."""
    if not path.is_file():
        return {}
    baseline: dict[str, ViolationFingerprint] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 4:
            continue
        entry = ViolationFingerprint(
            path=parts[0],
            snippet_hash=parts[1],
            category=parts[2],
            owner_epic=parts[3],
        )
        baseline[entry.key] = entry
    return baseline


def write_fingerprint_baseline(
    fingerprints: list[ViolationFingerprint],
    path: Path = FINGERPRINT_BASELINE_PATH,
) -> None:
    """Write stable legacy fingerprints to the baseline ratchet file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    unique = {item.key: item for item in fingerprints}
    lines = [
        "# path | normalized_snippet_hash | category | owner_epic",
        *(unique[key].format_line() for key in sorted(unique)),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_burndown_report(
    *,
    baseline: dict[str, ViolationFingerprint],
    current: list[ViolationFingerprint],
    output_path: Path,
) -> dict[str, object]:
    """Write PR burn-down artifact for legacy Dart-in-Python debt."""
    current_map = {item.key: item for item in current}
    removed = sorted(set(baseline) - set(current_map))
    added = sorted(set(current_map) - set(baseline))
    by_module = Counter(item.path.split("/")[0] for item in current)
    payload: dict[str, object] = {
        "baselineCount": len(baseline),
        "currentCount": len(current),
        "removed": removed,
        "added": added,
        "removedCount": len(removed),
        "addedCount": len(added),
        "byModule": dict(sorted(by_module.items())),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Dart-in-Python sniff linter")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write current layout/widgets count to baseline JSON",
    )
    parser.add_argument(
        "--migrate-baseline",
        action="store_true",
        help="Write fingerprint baseline for layout/widgets legacy debt",
    )
    parser.add_argument(
        "--write-burndown",
        type=Path,
        default=None,
        help="Write burn-down JSON report to the given path",
    )
    args = parser.parse_args()

    blocking = collect_blocking_violations()
    legacy = collect_legacy_fingerprints()
    layout_count = len(legacy)

    if args.migrate_baseline:
        write_fingerprint_baseline(legacy)
        print(f"Migrated {len(legacy)} legacy fingerprints to {FINGERPRINT_BASELINE_PATH}")
        return 0

    if args.update_baseline:
        COUNT_BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        COUNT_BASELINE_PATH.write_text(
            json.dumps(
                {
                    "layout_widgets_count": layout_count,
                    "total_blocking_count": len(blocking),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            f"Updated count baseline: layout/widgets={layout_count}, blocking={len(blocking)}",
        )
        return 0

    if not COUNT_BASELINE_PATH.is_file():
        print(f"Missing count baseline: {COUNT_BASELINE_PATH}", file=sys.stderr)
        return 1
    if not FINGERPRINT_BASELINE_PATH.is_file():
        print(f"Missing fingerprint baseline: {FINGERPRINT_BASELINE_PATH}", file=sys.stderr)
        return 1

    count_baseline = json.loads(COUNT_BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_layout = int(count_baseline.get("layout_widgets_count", 0))
    if layout_count > baseline_layout:
        print(
            "Dart sniff burn-down regression: "
            f"layout/widgets {layout_count} > baseline {baseline_layout}",
            file=sys.stderr,
        )
        return 1

    fingerprint_baseline = load_fingerprint_baseline()
    current_map = {item.key: item for item in legacy}
    new_fingerprints = sorted(set(current_map) - set(fingerprint_baseline))
    if new_fingerprints:
        print("New Dart sniff fingerprints outside allowlist:", file=sys.stderr)
        for key in new_fingerprints[:20]:
            print(f"  {key}", file=sys.stderr)
        if len(new_fingerprints) > 20:
            print(f"  ... and {len(new_fingerprints) - 20} more", file=sys.stderr)
        return 1

    if blocking:
        print("Blocking Dart sniff outside allowlist:", file=sys.stderr)
        for item in blocking[:20]:
            print(f"  {item.format_line()}", file=sys.stderr)
        if len(blocking) > 20:
            print(f"  ... and {len(blocking) - 20} more", file=sys.stderr)
        return 1

    if args.write_burndown is not None:
        payload = write_burndown_report(
            baseline=fingerprint_baseline,
            current=legacy,
            output_path=args.write_burndown,
        )
        print(
            "Burndown report: "
            f"baseline={payload['baselineCount']} current={payload['currentCount']} "
            f"removed={payload['removedCount']} added={payload['addedCount']}",
        )

    print(
        "Dart sniff OK "
        f"(layout/widgets={layout_count}, baseline_count={baseline_layout}, "
        f"fingerprints={len(fingerprint_baseline)})",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
