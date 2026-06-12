#!/usr/bin/env python3
"""Lint gate: forbid regex + string-splice Dart surgery outside sanctioned paths."""

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
SCAN_ROOT = ROOT / "src" / "figma_flutter_agent" / "generator" / "dart"
BASELINE_PATH = ROOT / "tests" / "fixtures" / "lint" / "regex_dart_surgery_baseline.txt"
OWNER_EPIC = "AST-sidecar"

_REGEX_USE_RE = re.compile(r"\bre\.(?:search|sub|match)\s*\(")
_SLICE_RE = re.compile(
    r"\b(?:block|inner|updated|current|builder_body)\s*\[|"
    r"\+\s*insert\s*\+|"
    r"\+\s*child_expr\s*\+",
)
_DART_ANCHOR_RE = re.compile(
    r"\bchild:\s*|Positioned|SizedBox|Container|FittedBox",
)


def _file_is_violation(text: str) -> bool:
    return (
        _REGEX_USE_RE.search(text) is not None
        and _SLICE_RE.search(text) is not None
        and _DART_ANCHOR_RE.search(text) is not None
    )


def collect_violations() -> list[ViolationFingerprint]:
    """Collect regex Dart surgery sites under generator/dart."""
    violations: list[ViolationFingerprint] = []
    for path in sorted(SCAN_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if not _file_is_violation(text):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for match in _REGEX_USE_RE.finditer(text):
            normalized = normalize_snippet(text, match.start())
            violations.append(
                ViolationFingerprint(
                    path=rel,
                    snippet_hash=snippet_hash(normalized),
                    category="regex_dart_surgery",
                    owner_epic=OWNER_EPIC,
                ),
            )
    return list({item.key: item for item in violations}.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Regex Dart surgery lint gate")
    parser.add_argument(
        "--migrate-baseline",
        action="store_true",
        help="Write current violations to the baseline file",
    )
    parser.add_argument(
        "--write-burndown",
        type=Path,
        default=None,
        help="Write burn-down JSON report to the given path",
    )
    args = parser.parse_args()

    current = collect_violations()

    if args.migrate_baseline:
        write_fingerprint_baseline(current, BASELINE_PATH)
        print(f"Migrated {len(current)} regex-dart fingerprints to {BASELINE_PATH}")
        return 0

    if not BASELINE_PATH.is_file():
        print(f"Missing regex Dart surgery baseline: {BASELINE_PATH}", file=sys.stderr)
        return 1

    baseline = load_fingerprint_baseline(BASELINE_PATH)
    comparison = compare_fingerprints(baseline, current)
    exit_code, errors = gate_exit_code(comparison, gate_name="Regex Dart surgery")
    for line in errors:
        print(line, file=sys.stderr)

    if args.write_burndown is not None:
        write_burndown_report(
            baseline=baseline,
            current=current,
            output_path=args.write_burndown,
            comparison=comparison,
        )

    if exit_code != 0:
        return exit_code

    print(f"Regex Dart surgery OK (fingerprints={len(current)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
