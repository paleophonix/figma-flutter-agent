"""Extracted-widget root sanitization and parent-data emit guards."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.subtree.blocks import _find_matching_paren

_WIDGET_BUILD_RETURN_RE = re.compile(
    r"Widget\s+build\s*\([^)]*\)\s*\{[^{}]*?return\s+([^;]+);",
    re.DOTALL,
)


def _extract_top_level_named_child(inner: str, name: str) -> str | None:
    """Return the expression after ``name:`` at paren depth zero inside ``inner``."""
    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    needle = f"{name}:"
    index = 0
    while index < len(inner):
        if inner.startswith(needle, index) and depth == 0:
            cursor = index + len(needle)
            while cursor < len(inner) and inner[cursor].isspace():
                cursor += 1
            expr_start = cursor
            expr_depth = 0
            in_str = False
            str_q = ""
            esc = False
            while cursor < len(inner):
                ch = inner[cursor]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == str_q:
                        in_str = False
                    cursor += 1
                    continue
                if ch in {"'", '"'}:
                    in_str = True
                    str_q = ch
                    cursor += 1
                    continue
                if ch == "(":
                    expr_depth += 1
                elif ch == ")":
                    if expr_depth == 0:
                        break
                    expr_depth -= 1
                elif ch == "," and expr_depth == 0:
                    break
                cursor += 1
            return inner[expr_start:cursor].strip()
        ch = inner[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == string_quote:
                in_string = False
            index += 1
            continue
        if ch in {"'", '"'}:
            in_string = True
            string_quote = ch
            index += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        index += 1
    return None


def strip_stack_parent_data_wrappers(widget: str) -> str:
    """Remove ``Positioned`` wrappers from a widget expression root.

    Extracted reusable widgets must return local content; the layout call-site
    owns stack placement inside a ``Stack``.

    Args:
        widget: Dart widget expression emitted for an extracted widget body.

    Returns:
        Widget expression with outer ``Positioned`` wrappers removed.
    """
    result = widget.strip()
    while result.startswith("Positioned("):
        open_paren = result.index("(")
        close_paren = _find_matching_paren(result, open_paren)
        if close_paren is None:
            break
        inner = result[open_paren + 1 : close_paren]
        child = _extract_top_level_named_child(inner, "child")
        if child is None:
            break
        result = child.strip()
    return result


def validate_widget_build_has_no_parent_data_root(source: str) -> list[str]:
    """Return violations when a widget ``build`` returns a Stack parent-data root.

    Args:
        source: Full Dart widget file source.

    Returns:
        Human-readable violation messages; empty when compliant.
    """
    match = _WIDGET_BUILD_RETURN_RE.search(source)
    if match is None:
        return []
    returned = match.group(1).strip()
    if returned.startswith("Positioned("):
        return ["positioned_requires_stack_ancestor: widget build must not return Positioned"]
    return []
