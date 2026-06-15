"""Write legacy heuristic burn-down fingerprints for semantics signoff."""

from __future__ import annotations

import argparse
import json
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
    write_fingerprint_baseline,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "figma_flutter_agent"
INTERACTION = SRC / "parser" / "interaction"
LAYOUT = SRC / "generator" / "layout"
LAYOUT_FLEX_POLICY = LAYOUT / "flex_policy"
LAYOUT_EMIT = LAYOUT / "widgets" / "emit"
FINGERPRINT_BASELINE = (
    ROOT / "tests" / "fixtures" / "semantics" / "legacy_predicate_fingerprints.txt"
)
OWNER_EPIC = "E5"

_PREDICATE_CALL_RE = re.compile(
    r"\b(?P<name>(?:looks_like|row_is|stack_is|column_is|hosts|is_compact|is_centered)_[A-Za-z0-9_]+)\s*\(",
)
_LEXICON_RE = re.compile(r"^_[A-Z0-9_]+(?:_HINTS|_LABELS)\s*=\s*frozenset\(")
_STRING_SNIFF_RE = re.compile(r"_label_matches_action_hint|in normalized for hint in")
_NAME_HINT_RE = re.compile(
    r'"input" in name|"button" in name|"btn" in name|"card" in name|'
    r"match_semantic_type_from_name_fallback|leaf_type_used_name_hint|"
    r'_INPUT_HINTS|"password" in',
)

ZONE_ROOTS: tuple[tuple[str, Path], ...] = (
    ("interaction", INTERACTION),
    ("layout_flex_policy", LAYOUT_FLEX_POLICY),
    ("layout_emit", LAYOUT_EMIT),
    ("layout_other", LAYOUT),
)

PARSER_ZONE_FILES: tuple[tuple[str, Path], ...] = (
    ("parser_tree", SRC / "parser" / "tree_node.py"),
    ("parser_forms", SRC / "parser" / "interaction" / "forms.py"),
)


def _iter_zone_files(zone: str, root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        if zone == "layout_other" and (
            path.resolve().is_relative_to(LAYOUT_FLEX_POLICY.resolve())
            or path.resolve().is_relative_to(LAYOUT_EMIT.resolve())
        ):
            continue
        files.append(path)
    return files


def collect_predicate_fingerprints() -> list[ViolationFingerprint]:
    """Collect archetype predicate call/definition fingerprints by zone."""
    fingerprints: list[ViolationFingerprint] = []
    for zone, root in ZONE_ROOTS:
        if not root.is_dir():
            continue
        for path in _iter_zone_files(zone, root):
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            for match in _PREDICATE_CALL_RE.finditer(text):
                normalized = normalize_snippet(text, match.start())
                fingerprints.append(
                    ViolationFingerprint(
                        path=rel,
                        snippet_hash=snippet_hash(normalized),
                        category=f"archetype_predicate_call:{zone}",
                        owner_epic=OWNER_EPIC,
                    ),
                )
    return fingerprints


def collect_lexicon_fingerprints() -> list[ViolationFingerprint]:
    """Collect domain lexicon entry fingerprints under interaction."""
    fingerprints: list[ViolationFingerprint] = []
    for path in sorted(INTERACTION.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for line_no, line in enumerate(text.splitlines(), start=1):
            if _LEXICON_RE.match(line.strip()):
                normalized = f"{rel}:{line_no}:{line.strip()}"
                fingerprints.append(
                    ViolationFingerprint(
                        path=rel,
                        snippet_hash=snippet_hash(normalized),
                        category="domain_lexicon",
                        owner_epic=OWNER_EPIC,
                    ),
                )
    return fingerprints


def collect_string_sniff_fingerprints() -> list[ViolationFingerprint]:
    """Collect string-sniff helper fingerprints under interaction."""
    fingerprints: list[ViolationFingerprint] = []
    for path in sorted(INTERACTION.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for match in _STRING_SNIFF_RE.finditer(text):
            normalized = normalize_snippet(text, match.start())
            fingerprints.append(
                ViolationFingerprint(
                    path=rel,
                    snippet_hash=snippet_hash(normalized),
                    category="string_sniff",
                    owner_epic=OWNER_EPIC,
                ),
            )
    return fingerprints


def collect_parser_name_hint_fingerprints() -> list[ViolationFingerprint]:
    """Collect parse-time layer-name heuristic fingerprints (audit-only containment)."""
    fingerprints: list[ViolationFingerprint] = []
    for zone, path in PARSER_ZONE_FILES:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for match in _NAME_HINT_RE.finditer(text):
            normalized = normalize_snippet(text, match.start())
            fingerprints.append(
                ViolationFingerprint(
                    path=rel,
                    snippet_hash=snippet_hash(normalized),
                    category=f"name_hint:{zone}",
                    owner_epic=OWNER_EPIC,
                ),
            )
    return fingerprints


def collect_all_fingerprints() -> list[ViolationFingerprint]:
    """Collect all semantics legacy heuristic fingerprints."""
    combined = (
        collect_predicate_fingerprints()
        + collect_lexicon_fingerprints()
        + collect_string_sniff_fingerprints()
        + collect_parser_name_hint_fingerprints()
    )
    return list({item.key: item for item in combined}.values())


def collect_zone_counts(fingerprints: list[ViolationFingerprint]) -> dict[str, int]:
    """Count predicate and parser name-hint fingerprints per zone."""
    counts = {zone: 0 for zone, _ in ZONE_ROOTS}
    counts.update({zone: 0 for zone, _ in PARSER_ZONE_FILES})
    for item in fingerprints:
        if item.category.startswith(("archetype_predicate_call:", "name_hint:")):
            zone = item.category.split(":", 1)[1]
            counts[zone] = counts.get(zone, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantics legacy burn-down report")
    parser.add_argument(
        "--write-report",
        type=Path,
        required=True,
        help="Output JSON path",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=FINGERPRINT_BASELINE,
        help="Fingerprint baseline for legacy heuristic debt",
    )
    parser.add_argument(
        "--migrate-baseline",
        action="store_true",
        help="Write current fingerprints to the baseline file",
    )
    parser.add_argument(
        "--allow-missing-baseline",
        action="store_true",
        help="Write advisory report even when the committed baseline is missing",
    )
    args = parser.parse_args()

    current = collect_all_fingerprints()
    zones = collect_zone_counts(current)

    if args.migrate_baseline:
        write_fingerprint_baseline(current, args.baseline)
        print(f"Migrated {len(current)} semantics fingerprints to {args.baseline}")
        return 0

    if not args.baseline.is_file():
        payload: dict[str, object] = {
            "zones": zones,
            "fingerprint_ok": False,
            "baseline_missing": args.baseline.as_posix(),
        }
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.allow_missing_baseline:
            raise SystemExit(f"Semantics legacy burn-down baseline missing: {args.baseline}")
        return 1

    baseline = load_fingerprint_baseline(args.baseline)
    comparison = compare_fingerprints(baseline, current)
    exit_code, errors = gate_exit_code(comparison, gate_name="Semantics legacy burndown")
    payload = {
        "zones": zones,
        "fingerprint_ok": comparison.ok,
        "baselineCount": len(baseline),
        "currentCount": len(current),
        "added": list(comparison.added),
        "removed": list(comparison.removed),
        "relocated": list(comparison.relocated),
    }
    args.write_report.parent.mkdir(parents=True, exist_ok=True)
    args.write_report.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return exit_code

    print(
        f"Semantics legacy burndown OK (fingerprints={len(current)}, zones={zones})",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
