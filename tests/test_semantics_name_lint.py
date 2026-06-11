"""Ban layer-name and label matching inside parser/semantics."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEMANTICS_ROOT = REPO_ROOT / "src" / "figma_flutter_agent" / "parser" / "semantics"

FORBIDDEN_ATTRS = frozenset({"name"})
FORBIDDEN_TEXT_ATTRS = frozenset({"text"})


class _SemanticsNameVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.offenders: list[str] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.attr, str):
            if node.attr in FORBIDDEN_ATTRS:
                self.offenders.append(f"{node.lineno}: .{node.attr}")
            if node.attr in FORBIDDEN_TEXT_ATTRS and _is_clean_node_text_access(node):
                self.offenders.append(f"{node.lineno}: .text")
        self.generic_visit(node)


def _is_clean_node_text_access(node: ast.Attribute) -> bool:
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return isinstance(current, ast.Name) and current.id in {"node", "clean_node", "child"}


def test_semantics_package_avoids_name_and_label_matching() -> None:
    offenders: list[str] = []
    for path in sorted(SEMANTICS_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        visitor = _SemanticsNameVisitor()
        visitor.visit(tree)
        for item in visitor.offenders:
            rel = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{rel}:{item}")
    assert offenders == [], f"name/label matching in semantics: {offenders}"
