"""Standalone Dart syntax cleanup regexes."""

from __future__ import annotations

import re

_BROKEN_ARTBOARD_DOUBLE_FROM_ENV = re.compile(
    r"(?:const|static\s+final)\s+double\s+(_artboardPreview(?:Width|Height))\s*=\s*"
    r"double\.fromEnvironment\s*\(\s*['\"](?P<define>[^'\"]+)['\"]\s*\)\s*;?",
    re.MULTILINE,
)

_TRANSPARENT_MATERIAL_RE = re.compile(
    r"Material\(\s*\n?\s*type:\s*MaterialType\.transparency,\s*\n?\s*child:\s*",
    re.MULTILINE,
)


def repair_broken_artboard_preview_declarations(source: str) -> str:
    """Fix LLM-corrupted ``double.fromEnvironment`` artboard preview static fields."""
    if "double.fromEnvironment" not in source:
        return source

    def _replace(match: re.Match[str]) -> str:
        field = match.group(1)
        define = match.group("define")
        return (
            f"static final double {field} = double.tryParse(\n"
            f"    const String.fromEnvironment('{define}'),\n"
            f"  ) ??\n"
            f"  0;"
        )

    return _BROKEN_ARTBOARD_DOUBLE_FROM_ENV.sub(_replace, source)


def unwrap_transparent_material_wrappers(source: str) -> str:
    """Remove ``Material(type: MaterialType.transparency, child: X)`` wrappers."""
    return _TRANSPARENT_MATERIAL_RE.sub("", source)
