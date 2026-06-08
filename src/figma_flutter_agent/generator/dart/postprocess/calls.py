"""Named-argument call repairs for generated Dart."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.delimiters import find_matching_paren


def split_top_level_commas(segment: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    start = 0
    for index, char in enumerate(segment):
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
        if char in "([{":
            depth += 1
            continue
        if char in ")]}":
            depth -= 1
            continue
        if char == "," and depth == 0:
            parts.append(segment[start:index])
            start = index + 1
    tail = segment[start:]
    if tail.strip():
        parts.append(tail)
    return parts


def repair_obsolete_dart_default_colons(source: str) -> str:
    """Rewrite pre-Dart 2.0 ``this.field : value`` defaults to ``this.field = value``."""
    return re.sub(
        r"(this\.\w+)\s*:\s*(?=['\"(\[\d])",
        r"\1 = ",
        source,
    )


def sanitize_named_only_widget_calls(
    source: str,
    *,
    widget_names: tuple[str, ...],
) -> str:
    """Drop stray positional args on custom widgets that only accept named parameters."""
    updated = source
    for widget_name in widget_names:
        opener = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(widget_name)}\s*\(")
        index = 0
        parts: list[str] = []
        while True:
            match = opener.search(updated, index)
            if match is None:
                parts.append(updated[index:])
                break
            start = match.start()
            parts.append(updated[index:start])
            paren_start = match.end() - 1
            paren_end = find_matching_paren(updated, paren_start)
            if paren_end is None:
                parts.append(updated[start:])
                break
            inner = updated[paren_start + 1 : paren_end]
            inner_stripped = inner.strip()
            if inner_stripped.startswith("{"):
                parts.append(updated[start : paren_end + 1])
                index = paren_end + 1
                continue
            if re.search(r"\b(?:required\s+)?this\.\w+", inner_stripped):
                parts.append(updated[start : paren_end + 1])
                index = paren_end + 1
                continue
            segments = split_top_level_commas(inner)
            named = [segment.strip() for segment in segments if segment.strip() and ":" in segment]
            if not named:
                parts.append(f"{widget_name}(onPressed: () {{}})")
            else:
                if not any(segment.startswith("onPressed") for segment in named):
                    named.insert(0, "onPressed: () {}")
                parts.append(f"{widget_name}({', '.join(named)})")
            index = paren_end + 1
        updated = "".join(parts)
    return updated
