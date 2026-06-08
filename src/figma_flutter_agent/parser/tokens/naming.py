"""Dart-safe design-token naming."""

from __future__ import annotations

import re

_NAME_SANITIZER = re.compile(r"[^a-zA-Z0-9]+")

_DART_KEYWORDS = frozenset(
    {
        "abstract",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "covariant",
        "default",
        "deferred",
        "do",
        "dynamic",
        "else",
        "enum",
        "export",
        "extends",
        "extension",
        "external",
        "factory",
        "false",
        "final",
        "finally",
        "for",
        "Function",
        "get",
        "hide",
        "if",
        "implements",
        "import",
        "in",
        "interface",
        "is",
        "late",
        "library",
        "mixin",
        "new",
        "null",
        "on",
        "operator",
        "part",
        "required",
        "rethrow",
        "return",
        "sealed",
        "set",
        "show",
        "static",
        "super",
        "switch",
        "sync",
        "this",
        "throw",
        "true",
        "try",
        "typedef",
        "var",
        "void",
        "when",
        "while",
        "with",
        "yield",
    }
)


def _normalize_dart_identifier(name: str) -> str:
    if not name:
        return "tToken"
    if name[0].isdigit() or name in _DART_KEYWORDS:
        return f"t{name[0].upper()}{name[1:]}"
    return name


def sanitize_token_name(name: str) -> str:
    """Convert a Figma style name to a Dart-safe camelCase token name."""
    parts = [part for part in _NAME_SANITIZER.split(name) if part]
    if not parts:
        return "tToken"
    head, *tail = parts
    candidate = head.lower() + "".join(part.capitalize() for part in tail)
    return _normalize_dart_identifier(candidate)


def allocate_token_name(base: str, used: set[str]) -> str:
    """Return a unique Dart token name, suffixing with ``2``, ``3``, ... on collision."""
    if base not in used:
        used.add(base)
        return base
    index = 2
    while True:
        candidate = f"{base}{index}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1
