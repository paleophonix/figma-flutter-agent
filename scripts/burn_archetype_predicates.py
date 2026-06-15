"""One-shot rename of legacy archetype predicates to layout_fact_* (Wave F burndown)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "figma_flutter_agent"
TESTS = ROOT / "tests"

_OLD_NAME_RE = re.compile(
    r"\b(?P<name>(?:looks_like|row_is|stack_is|column_is|hosts|is_compact|is_centered)_[A-Za-z0-9_]+)\b"
)


def _new_name(old: str) -> str:
    if old.startswith("looks_like_"):
        return "layout_fact_" + old.removeprefix("looks_like_")
    if old.startswith("row_is_"):
        return "layout_fact_row_" + old.removeprefix("row_is_")
    if old.startswith("stack_is_"):
        return "layout_fact_stack_" + old.removeprefix("stack_is_")
    if old.startswith("column_is_"):
        return "layout_fact_column_" + old.removeprefix("column_is_")
    if old.startswith("hosts_"):
        return "layout_fact_hosts_" + old.removeprefix("hosts_")
    if old.startswith("is_compact_"):
        return "layout_fact_compact_" + old.removeprefix("is_compact_")
    if old.startswith("is_centered_"):
        return "layout_fact_centered_" + old.removeprefix("is_centered_")
    return "layout_fact_" + old


def _collect_names(text: str) -> set[str]:
    return set(_OLD_NAME_RE.findall(text))


def _rename_in_text(text: str, mapping: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        return mapping.get(match.group("name"), match.group("name"))

    return _OLD_NAME_RE.sub(repl, text)


def main() -> None:
    mapping: dict[str, str] = {}
    paths: list[Path] = []
    for root in (SRC, TESTS):
        paths.extend(root.rglob("*.py"))

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for name in _collect_names(text):
            mapping.setdefault(name, _new_name(name))

    print(f"Renaming {len(mapping)} predicate symbols")
    for path in paths:
        original = path.read_text(encoding="utf-8")
        updated = _rename_in_text(original, mapping)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            print("updated", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
