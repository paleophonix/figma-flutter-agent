"""Write legacy heuristic burn-down counters for semantics signoff."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERACTION = ROOT / "src" / "figma_flutter_agent" / "parser" / "interaction"
BASELINE = ROOT / "logs" / "semantics" / "legacy_burndown_baseline.json"

_PREDICATE_RE = re.compile(r"^def (looks_like_[A-Za-z0-9_]+)")
_LEXICON_RE = re.compile(r"^_[A-Z0-9_]+(?:_HINTS|_LABELS)\s*=\s*frozenset\(")
_STRING_SNIFF_RE = re.compile(r"_label_matches_action_hint|in normalized for hint in")


def _count_file_patterns(root: Path, pattern: re.Pattern[str]) -> int:
    total = 0
    for path in root.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if pattern.search(line.strip()):
                total += 1
    return total


def collect_counts() -> dict[str, int]:
    """Collect predicate, lexicon, and string-sniff counters."""
    predicates = _count_file_patterns(INTERACTION, _PREDICATE_RE)
    predicates += _count_file_patterns(
        ROOT / "src" / "figma_flutter_agent" / "generator" / "layout" / "flex_policy",
        _PREDICATE_RE,
    )
    lexicon = 0
    for path in INTERACTION.rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if _LEXICON_RE.match(line.strip()):
                lexicon += 1
    string_sniff = 0
    for path in INTERACTION.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        string_sniff += len(_STRING_SNIFF_RE.findall(text))
    return {
        "archetype_predicates": predicates,
        "domain_lexicon_entries": lexicon,
        "string_sniff_sites": string_sniff,
    }


def main() -> None:
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
        default=BASELINE,
        help="Optional baseline JSON for monotonic decrease check",
    )
    args = parser.parse_args()
    counts = collect_counts()
    payload: dict[str, object] = {"counts": counts, "monotonic_ok": True}
    if args.baseline.is_file():
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline_counts = baseline.get("counts", baseline)
        monotonic = all(
            counts[key] <= int(baseline_counts[key])
            for key in counts
            if key in baseline_counts
        )
        payload["monotonic_ok"] = monotonic
        payload["baseline"] = baseline_counts
    args.write_report.parent.mkdir(parents=True, exist_ok=True)
    args.write_report.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
