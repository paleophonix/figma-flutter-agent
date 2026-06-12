#!/usr/bin/env python3
"""Lint gate: forbid load_settings() inside compiler internals."""

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
    snippet_hash,
    write_burndown_report,
    write_fingerprint_baseline,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "figma_flutter_agent"
SCAN_ROOTS = (
    SRC / "generator",
    SRC / "parser",
)
ALLOWLIST_PREFIXES = (
    SRC / "config",
    SRC / "cli",
    SRC / "pipeline",
    SRC / "stages",
)
BASELINE_PATH = ROOT / "tests" / "fixtures" / "lint" / "settings_purity_baseline.txt"
OWNER_EPIC = "E2.6"
_LOAD_SETTINGS_RE = re.compile(r"\bload_settings\s*\(")


def _is_allowlisted(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved.is_relative_to(prefix.resolve()) for prefix in ALLOWLIST_PREFIXES)


def collect_violations() -> list[ViolationFingerprint]:
    """Collect load_settings() call sites in compiler scan roots."""
    violations: list[ViolationFingerprint] = []
    for scan_root in SCAN_ROOTS:
        if not scan_root.is_dir():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            if _is_allowlisted(path):
                continue
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            for line_no, line in enumerate(text.splitlines(), start=1):
                if not _LOAD_SETTINGS_RE.search(line):
                    continue
                normalized = f"{rel}:{line_no}:{line.strip()}"
                violations.append(
                    ViolationFingerprint(
                        path=rel,
                        snippet_hash=snippet_hash(normalized),
                        category="load_settings_call",
                        owner_epic=OWNER_EPIC,
                    ),
                )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Settings purity lint gate")
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
        print(f"Migrated {len(current)} settings-purity fingerprints to {BASELINE_PATH}")
        return 0

    if not BASELINE_PATH.is_file():
        print(f"Missing settings purity baseline: {BASELINE_PATH}", file=sys.stderr)
        return 1

    baseline = load_fingerprint_baseline(BASELINE_PATH)
    comparison = compare_fingerprints(baseline, current)
    exit_code, errors = gate_exit_code(comparison, gate_name="Settings purity")
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

    print(f"Settings purity OK (fingerprints={len(current)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
