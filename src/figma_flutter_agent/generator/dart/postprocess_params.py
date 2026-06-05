"""Named-parameter stripping for planned reconcile (delimiter-based, not layout AST)."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.delimiters import find_matching_paren


def strip_named_parameter(source: str, param_name: str) -> str:
    token = f"{param_name}:"
    parts: list[str] = []
    index = 0
    while index < len(source):
        match = source.find(token, index)
        if match == -1:
            parts.append(source[index:])
            break
        parts.append(source[index:match])
        value_start = match + len(token)
        while value_start < len(source) and source[value_start].isspace():
            value_start += 1
        value_end = _value_end(source, value_start)
        trailing = value_end
        while trailing < len(source) and source[trailing].isspace():
            trailing += 1
        if trailing < len(source) and source[trailing] == ",":
            trailing += 1
        index = trailing
    return "".join(parts)


def _value_end(source: str, start: int) -> int:
    if start >= len(source):
        return start
    char = source[start]
    if char == "(":
        close = find_matching_paren(source, start)
        return start if close is None else close + 1
    if char == "[":
        depth = 0
        for index in range(start, len(source)):
            if source[index] == "[":
                depth += 1
            elif source[index] == "]":
                depth -= 1
                if depth == 0:
                    return index + 1
        return start
    if char in {"'", '"'}:
        quote = char
        escape = False
        for index in range(start + 1, len(source)):
            current = source[index]
            if escape:
                escape = False
                continue
            if current == "\\":
                escape = True
                continue
            if current == quote:
                return index + 1
        return len(source)
    token_match = re.match(r"[\w.]+", source[start:])
    if token_match is not None:
        return start + token_match.end()
    return start + 1
