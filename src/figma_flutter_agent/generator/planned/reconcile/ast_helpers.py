"""Pure Dart string utilities — no I/O, no planned dict."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.postprocess_params import strip_named_parameter

_WIDGET_CLASS_RE = re.compile(
    r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)


def _primary_public_widget_class_name(content: str) -> str | None:
    """Return the exported widget class, ignoring private layout helper widgets."""
    public_names = [
        match.group("name")
        for match in _WIDGET_CLASS_RE.finditer(content)
        if not match.group("name").startswith("_")
    ]
    if not public_names:
        return None
    widget_names = [name for name in public_names if name.endswith("Widget")]
    if widget_names:
        return widget_names[-1]
    return public_names[-1]


def _widget_declares_param(widget_source: str, param_name: str) -> bool:
    patterns = (
        rf"\bthis\.{re.escape(param_name)}\b",
        rf"\bfinal\s+\w+\s+{re.escape(param_name)}\b",
        rf"\brequired\s+this\.{re.escape(param_name)}\b",
    )
    return any(re.search(pattern, widget_source) for pattern in patterns)


def _strip_named_param_in_widget_calls(
    source: str,
    class_name: str,
    param_name: str,
) -> str:
    parts: list[str] = []
    index = 0
    while True:
        start = source.find(class_name, index)
        if start == -1:
            parts.append(source[index:])
            break
        parts.append(source[index:start])
        paren_start = source.find("(", start)
        if paren_start == -1 or paren_start > start + len(class_name) + 2:
            parts.append(source[start : start + len(class_name)])
            index = start + len(class_name)
            continue
        paren_end = _find_matching_paren(source, paren_start)
        if paren_end is None:
            parts.append(source[start:])
            break
        block = source[start : paren_end + 1]
        parts.append(strip_named_parameter(block, param_name))
        index = paren_end + 1
    return "".join(parts)


def _find_matching_paren(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "(":
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(open_index, len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == string_quote:
                in_string = False
            continue

        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _find_matching_brace(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "{":
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(open_index, len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == string_quote:
                in_string = False
            continue

        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _iter_top_level_brace_inners(source: str) -> list[str]:
    """Return inner text for each ``{...}`` block using linear brace matching."""
    inners: list[str] = []
    index = 0
    length = len(source)
    while index < length:
        while index < length and source[index] != "{":
            index += 1
        if index >= length:
            break
        close = _find_matching_brace(source, index)
        if close is None:
            break
        inners.append(source[index + 1 : close])
        index = close + 1
    return inners
