#!/usr/bin/env python3
"""Lint gate: forbid anonymous color/typography literals in emit strings."""

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
SCAN_ROOTS = (
    ROOT / "src" / "figma_flutter_agent" / "generator",
    ROOT / "src" / "figma_flutter_agent" / "parser" / "interaction",
)
BASELINE_PATH = ROOT / "tests" / "fixtures" / "lint" / "hardcoded_color_baseline.txt"
OWNER_EPIC = "E5"
ALLOW_COMMENT = "# lint:allow"
SYSTEM_OVERLAY_LITERALS = frozenset(
    {
        "0x00000000",
        "0xFFFFFFFF",
        "0x1A000000",
        "0x0D000000",
        "0x3D000000",
        "0xFF000000",
    },
)
_WHITELIST_PATH_PARTS = frozenset(
    {
        "generator/variant/controls.py",
        "generator/layout/cupertino.py",
        "generator/layout/style/colors.py",
        "generator/renderer_theme.py",
    },
)
_COLOR_LITERAL_RE = re.compile(
    r"(?:const\s+)?Color\(\s*(0x[0-9A-Fa-f]{8})\s*\)",
)
_HEX_STRING_RE = re.compile(r"""["']0xFF[0-9A-Fa-f]{6}["']""")
_EMIT_FONT_SIZE_RE = re.compile(
    r"""fontSize:\s*\d+(?:\.\d+)?""",
)


def _line_has_allow_comment(lines: list[str], line_index: int) -> bool:
    return any(ALLOW_COMMENT in lines[index] for index in (line_index, line_index - 1))


def _is_whitelisted(path: str) -> bool:
    return any(part in path for part in _WHITELIST_PATH_PARTS)


def _scan_file(path: Path, violations: list[ViolationFingerprint]) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = path.relative_to(ROOT).as_posix()
    if _is_whitelisted(rel):
        return

    for match in _COLOR_LITERAL_RE.finditer(text):
        literal = match.group(1)
        line_no = text.count("\n", 0, match.start())
        if literal.upper() in SYSTEM_OVERLAY_LITERALS and _line_has_allow_comment(
            lines, line_no
        ):
            continue
        normalized = normalize_snippet(text, match.start())
        violations.append(
            ViolationFingerprint(
                path=rel,
                snippet_hash=snippet_hash(normalized),
                category="hardcoded_color_literal",
                owner_epic=OWNER_EPIC,
            ),
        )

    for match in _HEX_STRING_RE.finditer(text):
        line_no = text.count("\n", 0, match.start())
        if _line_has_allow_comment(lines, line_no):
            continue
        normalized = normalize_snippet(text, match.start())
        violations.append(
            ViolationFingerprint(
                path=rel,
                snippet_hash=snippet_hash(normalized),
                category="hardcoded_hex_string",
                owner_epic=OWNER_EPIC,
            ),
        )

    if "/widgets/" in rel.replace("\\", "/"):
        for match in _EMIT_FONT_SIZE_RE.finditer(text):
            line_no = text.count("\n", 0, match.start())
            if _line_has_allow_comment(lines, line_no):
                continue
            normalized = normalize_snippet(text, match.start())
            violations.append(
                ViolationFingerprint(
                    path=rel,
                    snippet_hash=snippet_hash(normalized),
                    category="hardcoded_font_size",
                    owner_epic=OWNER_EPIC,
                ),
            )


def collect_violations() -> list[ViolationFingerprint]:
    """Collect hardcoded color and typography literals in emit/parser paths."""
    violations: list[ViolationFingerprint] = []
    for scan_root in SCAN_ROOTS:
        if not scan_root.is_dir():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            _scan_file(path, violations)
    return list({item.key: item for item in violations}.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Hardcoded color lint gate")
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
        print(f"Migrated {len(current)} hardcoded-color fingerprints to {BASELINE_PATH}")
        return 0

    if not BASELINE_PATH.is_file():
        print(f"Missing hardcoded color baseline: {BASELINE_PATH}", file=sys.stderr)
        return 1

    baseline = load_fingerprint_baseline(BASELINE_PATH)
    comparison = compare_fingerprints(baseline, current)
    exit_code, errors = gate_exit_code(comparison, gate_name="Hardcoded colors")
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

    print(f"Hardcoded colors OK (fingerprints={len(current)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
