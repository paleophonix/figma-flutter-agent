"""Grandfather lint: parser type mutations outside allowlisted modules."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "figma_flutter_agent"

TYPE_ASSIGN_PATTERN = re.compile(
    r"(?:\bnode_type\s*=|\bclean(?:_node)?\.type\s*=|\bnode\.type\s*=|type=NodeType\.)",
)

ALLOWLIST_PREFIXES = (
    "parser/tree.py",
    "parser/tree_node.py",
    "parser/components.py",
    "parser/interaction/",
    "parser/layout/",
    "parser/boundaries/",
    "parser/dedup/",
    "parser/accessibility.py",
    "parser/geometry.py",
    "parser/prototype.py",
    "parser/text_normalize.py",
    "parser/stack_paint.py",
    "generator/",
    "pipeline/",
    "stages/",
    "fixtures/",
    "debug/",
    "validation/",
    "audit/",
    "parser/semantics/",
)


def _relative(path: Path) -> str:
    return path.relative_to(SRC_ROOT).as_posix()


def test_no_unmanaged_type_assignment_in_parser() -> None:
    """Fail when new ad-hoc type assignments appear outside the allowlist."""
    offenders: list[str] = []
    parser_root = SRC_ROOT / "parser"
    for path in sorted(parser_root.rglob("*.py")):
        rel = _relative(path)
        if any(rel.startswith(prefix) or rel == prefix for prefix in ALLOWLIST_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8")
        if TYPE_ASSIGN_PATTERN.search(text):
            offenders.append(rel)
    assert offenders == [], f"Unmanaged parser type mutations: {offenders}"
