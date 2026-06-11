#!/usr/bin/env python3
"""Lint for Dart widget string literals outside templates (EPIC 3.4)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR_ROOT = ROOT / "src" / "figma_flutter_agent" / "generator"
SCAN_ROOT = GENERATOR_ROOT
BLOCKING_ROOTS = (GENERATOR_ROOT / "ir",)
BASELINE_PATH = ROOT / "tests" / "fixtures" / "lint" / "dart_sniff_baseline.json"

PATTERNS = (
    re.compile(r"\bContainer\("),
    re.compile(r"\bSizedBox\("),
    re.compile(r"\bPositioned\("),
    re.compile(r"\bElevatedButton\("),
    re.compile(r"\bChoiceChip\("),
    re.compile(r"\bTextField\("),
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


def _is_allowlisted(path: Path) -> bool:
    resolved = path.resolve()
    return any(
        resolved.is_relative_to(prefix.resolve())
        for prefix in (*ALLOWLIST_PREFIXES, *DEBT_ZONE_PREFIXES)
    )


LAYOUT_WIDGETS_ROOT = SCAN_ROOT / "layout" / "widgets"


def count_blocking_sniffs() -> tuple[int, list[str]]:
    """Count blocking Dart sniff violations in clean emit zones (``generator/ir``)."""
    total = 0
    violations: list[str] = []
    for blocking_root in BLOCKING_ROOTS:
        for path in sorted(blocking_root.rglob("*.py")):
            if _is_allowlisted(path):
                continue
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT)
            for pattern in PATTERNS:
                for match in pattern.finditer(text):
                    total += 1
                    line = text.count("\n", 0, match.start()) + 1
                    violations.append(f"{rel}:{line}:{pattern.pattern}")
    return total, violations


def count_layout_widget_sniffs() -> int:
    """Count sniff patterns under layout/widgets (burn-down metric only)."""
    total = 0
    for path in sorted(LAYOUT_WIDGETS_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in PATTERNS:
            total += len(pattern.findall(text))
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Dart-in-Python sniff linter")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write current layout/widgets count to baseline JSON",
    )
    args = parser.parse_args()

    _, violations = count_blocking_sniffs()
    layout_count = count_layout_widget_sniffs()

    if args.update_baseline:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        total_blocking, _ = count_blocking_sniffs()
        BASELINE_PATH.write_text(
            json.dumps(
                {
                    "layout_widgets_count": layout_count,
                    "total_blocking_count": total_blocking,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            f"Updated baseline: layout_widgets_count={layout_count}, "
            f"blocking={total_blocking}",
        )
        return 0

    if not BASELINE_PATH.is_file():
        print(f"Missing baseline: {BASELINE_PATH}", file=sys.stderr)
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_layout = int(baseline.get("layout_widgets_count", 0))
    if layout_count > baseline_layout:
        print(
            f"Dart sniff burn-down regression: layout/widgets {layout_count} > baseline {baseline_layout}",
            file=sys.stderr,
        )
        return 1

    if violations:
        print("Blocking Dart sniff outside allowlist:", file=sys.stderr)
        for item in violations[:20]:
            print(f"  {item}", file=sys.stderr)
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more", file=sys.stderr)
        return 1

    print(f"Dart sniff OK (layout/widgets={layout_count}, baseline={baseline_layout})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
