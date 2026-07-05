"""Extracted-widget root sanitization and parent-data emit guards."""

from __future__ import annotations

import re

from figma_flutter_agent.errors import GenerationError
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


def _split_top_level_list(inner: str) -> list[str]:
    """Split a comma-separated list body at bracket/paren depth zero."""
    items: list[str] = []
    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    start = 0
    for index, ch in enumerate(inner):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == string_quote:
                in_string = False
            continue
        if ch in {"'", '"'}:
            in_string = True
            string_quote = ch
        elif ch in {"(", "[", "{"}:
            depth += 1
        elif ch in {")", "]", "}"}:
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(inner[start:index].strip())
            start = index + 1
    tail = inner[start:].strip()
    if tail:
        items.append(tail)
    return items


def _unwrap_single_positioned_child_stack(widget: str) -> str:
    """Unwrap a ``Stack`` whose only child is a ``Positioned`` to that child.

    A ``Stack`` with just positioned children has no intrinsic size (loose fit),
    so as an extracted-widget root it fails ``size.isFinite`` under an unbounded
    parent (``Column``/``ListView``). When the Stack holds a single ``Positioned``
    the wrapper is spurious — the call-site owns placement — so we drop it and let
    the ``Positioned`` strip below reduce to the bounded child. Multi-child stacks
    (overlapping content) are left intact.
    """
    result = widget.strip()
    if not result.startswith("Stack("):
        return result
    open_paren = result.index("(")
    close_paren = _find_matching_paren(result, open_paren)
    if close_paren is None or close_paren != len(result) - 1:
        return result
    children = _extract_top_level_named_child(result[open_paren + 1 : close_paren], "children")
    if children is None:
        return result
    children = children.strip()
    if not (children.startswith("[") and children.endswith("]")):
        return result
    items = _split_top_level_list(children[1:-1])
    if len(items) == 1 and items[0].startswith("Positioned("):
        return items[0]
    return result


def strip_stack_parent_data_wrappers(widget: str) -> str:
    """Remove ``Positioned`` wrappers from a widget expression root.

    Extracted reusable widgets must return local content; the layout call-site
    owns stack placement inside a ``Stack``.

    Args:
        widget: Dart widget expression emitted for an extracted widget body.

    Returns:
        Widget expression with outer ``Positioned`` wrappers removed.
    """
    result = _unwrap_single_positioned_child_stack(widget.strip())
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


def finalize_extracted_widget_body(body: str) -> str:
    """Strip stack parent-data wrappers from a reusable widget body expression.

    Args:
        body: Dart widget expression for an extracted widget ``build`` return.

    Returns:
        Sanitized widget expression safe as a standalone widget root.
    """
    return strip_stack_parent_data_wrappers(body)


def ensure_widget_file_no_parent_data_root(
    source: str,
    *,
    widget_name: str = "",
) -> None:
    """Raise when a generated widget file returns illegal parent-data roots.

    Args:
        source: Full Dart widget file source.
        widget_name: Optional widget label for error messages.

    Raises:
        GenerationError: When ``build`` returns ``Positioned`` or similar roots.
    """
    violations = validate_widget_build_has_no_parent_data_root(source)
    if violations:
        label = widget_name or "widget"
        raise GenerationError(f"extracted {label!r} violates emit invariant: {violations[0]}")


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
