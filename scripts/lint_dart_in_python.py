#!/usr/bin/env python3
"""Lint for Dart widget string literals outside templates (EPIC 3.4 / 4.5)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lint_baseline import (  # noqa: E402
    ViolationFingerprint,
    compare_fingerprints,
    gate_exit_code,
    load_fingerprint_baseline,
    normalize_snippet,
    snippet_hash,
    write_burndown_report,
    write_fingerprint_baseline,
)

ROOT = Path(__file__).resolve().parents[1]
GENERATOR_ROOT = ROOT / "src" / "figma_flutter_agent" / "generator"
SCAN_ROOT = GENERATOR_ROOT
BLOCKING_ROOTS = (GENERATOR_ROOT / "ir",)
FINGERPRINT_BASELINE_PATH = ROOT / "tests" / "fixtures" / "lint" / "emitter_baseline.txt"
DEFAULT_OWNER_EPIC = "E4.5"

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bContainer\("), "dart_widget_literal"),
    (re.compile(r"\bSizedBox\("), "dart_widget_literal"),
    (re.compile(r"\bPositioned\("), "dart_widget_literal"),
    (re.compile(r"\bElevatedButton\("), "dart_widget_literal"),
    (re.compile(r"\bChoiceChip\("), "dart_widget_literal"),
    (re.compile(r"\bTextField\("), "dart_widget_literal"),
)

ALLOWLIST_PREFIXES = (SCAN_ROOT / "templates",)

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


def _is_allowlisted(path: Path) -> bool:
    resolved = path.resolve()
    return any(
        resolved.is_relative_to(prefix.resolve())
        for prefix in (*ALLOWLIST_PREFIXES, *DEBT_ZONE_PREFIXES)
    )


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
            normalized = normalize_snippet(text, match.start())
            fingerprints.append(
                ViolationFingerprint(
                    path=rel,
                    snippet_hash=snippet_hash(normalized),
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Dart-in-Python sniff linter")
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

    if args.migrate_baseline:
        write_fingerprint_baseline(legacy, FINGERPRINT_BASELINE_PATH)
        print(f"Migrated {len(legacy)} legacy fingerprints to {FINGERPRINT_BASELINE_PATH}")
        return 0

    if not FINGERPRINT_BASELINE_PATH.is_file():
        print(f"Missing fingerprint baseline: {FINGERPRINT_BASELINE_PATH}", file=sys.stderr)
        return 1

    fingerprint_baseline = load_fingerprint_baseline(FINGERPRINT_BASELINE_PATH)
    comparison = compare_fingerprints(fingerprint_baseline, legacy)
    exit_code, errors = gate_exit_code(comparison, gate_name="Dart sniff")
    for line in errors:
        print(line, file=sys.stderr)

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
            comparison=comparison,
        )
        print(
            "Burndown report: "
            f"baseline={payload['baselineCount']} current={payload['currentCount']} "
            f"removed={payload['removedCount']} added={payload['addedCount']} "
            f"relocated={payload['relocatedCount']}",
        )

    if exit_code != 0:
        return exit_code

    print(
        f"Dart sniff OK (layout/widgets={len(legacy)}, fingerprints={len(fingerprint_baseline)})",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
