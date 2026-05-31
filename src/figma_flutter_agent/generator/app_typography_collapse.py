"""Collapse inline TextStyle literals to generated ``AppTypography`` tokens."""

from __future__ import annotations

import re

from figma_flutter_agent.schemas import DesignTokens, TypographyStyle

_FONT_SIZE_RE = re.compile(r"fontSize:\s*([\d.]+)")
_FONT_WEIGHT_RE = re.compile(r"fontWeight:\s*FontWeight\.(w\d+)")
_TEXT_STYLE_RE = re.compile(r"TextStyle\(([^)]*)\)", re.DOTALL)
_THEME_COPY_WITH_OPENER_RE = re.compile(
    r"Theme\.of\(context\)\.textTheme\.(\w+)\?\.copyWith\(",
)
_TEXT_RICH_OR_SPAN_CHILDREN_RE = re.compile(
    r"Text(?:\.rich)?\([^)]*TextSpan\(\s*children\s*:\s*\[",
    re.DOTALL,
)


def _theme_copywith_inside_text_rich(source: str, match_start: int) -> bool:
    """Do not rewrite ``copyWith`` inside ``Text.rich`` / ``TextSpan(children:`` — breaks nesting."""
    window = source[max(0, match_start - 800) : match_start]
    return _TEXT_RICH_OR_SPAN_CHILDREN_RE.search(window) is not None


def _token_entries(tokens: DesignTokens) -> list[tuple[str, TypographyStyle]]:
    return list(tokens.typography.items())


def _match_typography_token(
    font_size: float | None,
    font_weight: str | None,
    entries: list[tuple[str, TypographyStyle]],
) -> str | None:
    if font_size is None:
        return None
    best_name: str | None = None
    best_delta = float("inf")
    for name, token in entries:
        if token.font_size is None:
            continue
        delta = abs(float(token.font_size) - font_size)
        if delta > 0.6:
            continue
        if font_weight is not None and token.font_weight and token.font_weight != font_weight:
            continue
        if delta < best_delta:
            best_delta = delta
            best_name = name
    return best_name


def _strip_typography_fields(inner: str) -> str:
    stripped = re.sub(r"fontSize:\s*[\d.]+,?\s*", "", inner)
    stripped = re.sub(r"fontWeight:\s*FontWeight\.w\d+,?\s*", "", stripped)
    stripped = re.sub(
        r"fontFamilyFallback:\s*(?:const\s+)?\[[^\]]*\],?\s*",
        "",
        stripped,
        flags=re.DOTALL,
    )
    stripped = re.sub(r"fontFamily:\s*'[^']*',?\s*", "", stripped)
    stripped = re.sub(r"height:\s*[\d.]+,?\s*", "", stripped)
    stripped = re.sub(r"letterSpacing:\s*[\d.]+,?\s*", "", stripped)
    stripped = re.sub(r"leadingDistribution:[^,]+,?\s*", "", stripped)
    return stripped.strip().strip(",").strip()


def _ensure_app_typography_import(source: str, *, package_name: str) -> str:
    import_uri = f"package:{package_name}/theme/app_typography.dart"
    if import_uri in source or "app_typography.dart" in source:
        return source
    material = re.search(r"import\s+'package:flutter/material\.dart';\s*\n", source)
    if material is None:
        return source
    insert_at = material.end()
    return (
        source[:insert_at]
        + f"import '{import_uri}';\n"
        + source[insert_at:]
    )


def collapse_inline_text_styles_to_app_typography(
    source: str,
    tokens: DesignTokens | None,
    *,
    package_name: str = "demo_app",
) -> str:
    """Replace redundant inline font metrics with ``AppTypography.<token>``."""
    if re.search(r"\bclass\s+AppTypography\b", source):
        return source
    if tokens is None or not tokens.typography:
        return source
    entries = _token_entries(tokens)
    if not entries:
        return source

    updated = source

    def replace_text_style(match: re.Match[str]) -> str:
        inner = match.group(1)
        size_match = _FONT_SIZE_RE.search(inner)
        weight_match = _FONT_WEIGHT_RE.search(inner)
        font_size = float(size_match.group(1)) if size_match else None
        font_weight = weight_match.group(1) if weight_match else None
        token_name = _match_typography_token(font_size, font_weight, entries)
        if token_name is None:
            return match.group(0)
        remainder = _strip_typography_fields(inner)
        if remainder:
            return f"AppTypography.{token_name}.copyWith({remainder})"
        return f"AppTypography.{token_name}"

    updated = _TEXT_STYLE_RE.sub(replace_text_style, updated)

    from figma_flutter_agent.generator.dart_delimiters import find_matching_paren

    parts: list[str] = []
    cursor = 0
    for match in _THEME_COPY_WITH_OPENER_RE.finditer(updated):
        parts.append(updated[cursor : match.start()])
        paren_start = match.end() - 1
        paren_end = find_matching_paren(updated, paren_start)
        if paren_end is None:
            parts.append(updated[match.start() :])
            cursor = len(updated)
            break
        block = updated[match.start() : paren_end + 1]
        if _theme_copywith_inside_text_rich(updated, match.start()):
            parts.append(block)
            cursor = paren_end + 1
            continue
        inner = updated[paren_start + 1 : paren_end]
        size_match = _FONT_SIZE_RE.search(inner)
        weight_match = _FONT_WEIGHT_RE.search(inner)
        font_size = float(size_match.group(1)) if size_match else None
        font_weight = weight_match.group(1) if weight_match else None
        token_name = _match_typography_token(font_size, font_weight, entries)
        if token_name is None:
            parts.append(block)
        else:
            remainder = _strip_typography_fields(inner)
            if remainder:
                parts.append(f"AppTypography.{token_name}.copyWith({remainder})")
            else:
                parts.append(f"AppTypography.{token_name}")
        cursor = paren_end + 1
    parts.append(updated[cursor:])
    updated = "".join(parts)
    if "AppTypography." in updated:
        updated = _ensure_app_typography_import(updated, package_name=package_name)
        from figma_flutter_agent.generator.dart_syntax_repairs import (
            normalize_app_typography_style_references,
        )

        updated = normalize_app_typography_style_references(updated)
    return updated
