"""Multiline copy, RichText, and text patching utilities."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.delimiters import (
    find_matching_paren as _find_matching_paren,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_DART_STRING_LITERAL_RE = re.compile(
    r"""(['"])(?P<body>(?:\\.|(?!\1).)*)\1""",
    re.DOTALL,
)

_COPY_WIDTH_METRIC_SLACK = 1.06
_PROPORTIONAL_LEADING_MIN_LINE_HEIGHT = 1.15
_LINE_HEIGHT_RATIO_UPPER_BOUND = 3.0


def _copy_layout_width_for_metrics(figma_width: float) -> float:
    """Add slack so Flutter font metrics do not clip Figma-sized copy blocks."""
    slack_width = figma_width * _COPY_WIDTH_METRIC_SLACK
    return (
        round(slack_width, 1)
        if slack_width != int(slack_width)
        else float(int(slack_width))
    )


def _dart_single_quoted_literal(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f"'{escaped}'"


def _first_dart_string_body(source: str) -> str | None:
    """Return decoded content of the first Dart string literal in ``source``."""
    match = _DART_STRING_LITERAL_RE.search(source)
    if match is None:
        return None
    return match.group("body")


def _iter_dart_string_literals(source: str):
    """Yield ``(start, end, body)`` for each Dart string literal in ``source``."""
    for match in _DART_STRING_LITERAL_RE.finditer(source):
        yield match.start(), match.end(), match.group("body")


def sanitize_figma_display_text(text: str) -> str:
    """Normalize Figma copy for Flutter Text widgets."""
    updated = text.replace("\r\n", "\n")
    updated = re.sub(r"[ \t]+\n", "\n", updated)
    updated = re.sub(r"\n[ \t]+", "\n", updated)
    updated = updated.rstrip()
    if updated.endswith("\n"):
        updated = updated.rstrip("\n").rstrip()
    return updated


def _decode_dart_string_literal_content(text: str) -> str:
    """Decode escape sequences from a Dart single-quoted string body."""
    decoded: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "\\" or index + 1 >= len(text):
            decoded.append(char)
            index += 1
            continue
        escape = text[index + 1]
        if escape == "n":
            decoded.append("\n")
        elif escape == "r":
            decoded.append("\r")
        elif escape == "t":
            decoded.append("\t")
        elif escape == "\\":
            decoded.append("\\")
        elif escape == "'":
            decoded.append("'")
        elif escape == '"':
            decoded.append('"')
        else:
            decoded.append(escape)
        index += 2
    return "".join(decoded)


def _normalize_text_for_match(text: str, *, from_dart_literal: bool = False) -> str:
    if from_dart_literal:
        text = _decode_dart_string_literal_content(text)
    return " ".join(sanitize_figma_display_text(text).split())


def _figma_literal(text: str) -> str:
    return _dart_single_quoted_literal(sanitize_figma_display_text(text))


def _build_richtext_children_from_node(node: CleanDesignTreeNode) -> str:
    from figma_flutter_agent.generator.emit_text_span import (
        emit_text_span_children_from_node,
    )

    return ", ".join(emit_text_span_children_from_node(node))


def _patch_richtext_spans_from_tree(
    screen_code: str, clean_tree: CleanDesignTreeNode
) -> str:
    """Replace LLM RichText copy with Figma ``textSpans`` from the clean tree."""
    from .positioned import _collect_text_nodes

    updated = screen_code
    for node in _collect_text_nodes(clean_tree):
        if node.type != NodeType.TEXT or not node.text_spans:
            continue
        marker = _normalize_text_for_match(node.text or "")
        if not marker:
            continue
        rich_index = updated.find("RichText(")
        while rich_index != -1:
            paren_start = updated.find("(", rich_index)
            block_end = (
                _find_matching_paren(updated, paren_start)
                if paren_start != -1
                else None
            )
            if block_end is None:
                break
            block = updated[rich_index : block_end + 1]
            block_norm = _normalize_text_for_match(block)
            if marker not in block_norm and not any(
                _normalize_text_for_match(part.text) in block_norm
                for part in node.text_spans
            ):
                rich_index = updated.find("RichText(", rich_index + 1)
                continue
            spans_body = _build_richtext_children_from_node(node)
            align = "center"
            if "textAlign: TextAlign.left" in block:
                align = "left"
            elif "textAlign: TextAlign.right" in block:
                align = "right"
            replacement = (
                f"RichText(\n"
                f"                                      textAlign: TextAlign.{align},\n"
                f"                                      text: TextSpan(\n"
                f"                                        children: [{spans_body}],\n"
                f"                                      ),\n"
                f"                                    )"
            )
            updated = updated[:rich_index] + replacement + updated[block_end + 1 :]
            break
    return updated


def _extract_widget_style_expr(widget_block: str) -> str | None:
    """Return the full `style:` expression from a Text/RichText widget block."""
    marker = re.search(r"\bstyle:\s*", widget_block)
    if marker is None:
        return None
    index = marker.end()
    while index < len(widget_block) and widget_block[index].isspace():
        index += 1
    if index >= len(widget_block):
        return None
    if widget_block[index] in {"'", '"'}:
        quote = widget_block[index]
        index += 1
        escape = False
        while index < len(widget_block):
            char = widget_block[index]
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                index += 1
                break
            index += 1
    else:
        depth = 0
        while index < len(widget_block):
            char = widget_block[index]
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char == "," and depth == 0:
                break
            index += 1
    return widget_block[marker.end() : index].strip()


def _multiline_copy_line_widget(
    *,
    line_literal: str,
    style_expr: str,
    align_prefix: str,
) -> str:
    return (
        "FittedBox(\n"
        "                                      fit: BoxFit.scaleDown,\n"
        f"                                      child: Text({line_literal}, "
        f"{align_prefix}"
        "softWrap: false, "
        f"style: {style_expr}, "
        "textScaler: MediaQuery.textScalerOf(context)),\n"
        "                                    )"
    )


def _multiline_copy_text_widget(
    *,
    sanitized_text: str,
    style_expr: str,
    align_prefix: str,
) -> str:
    """Render Figma hard line breaks as one Text per line (no soft-wrap reflow)."""
    first_line, second_line = (part.strip() for part in sanitized_text.split("\n", 1))
    if not first_line or not second_line:
        literal = _figma_literal(sanitized_text)
        return (
            f"Text({literal}, "
            f"{align_prefix}"
            "softWrap: false, "
            f"style: {style_expr}, "
            "textScaler: MediaQuery.textScalerOf(context))"
        )
    return (
        "Column(\n"
        "                                  mainAxisSize: MainAxisSize.min,\n"
        "                                  children: [\n"
        f"                                    {_multiline_copy_line_widget(line_literal=_figma_literal(first_line), style_expr=style_expr, align_prefix=align_prefix)},\n"
        f"                                    {_multiline_copy_line_widget(line_literal=_figma_literal(second_line), style_expr=style_expr, align_prefix=align_prefix)},\n"
        "                                  ],\n"
        "                                )"
    )


def collapse_nested_fitted_box_wrappers(screen_code: str) -> str:
    """Unwrap redundant ``FittedBox`` > ``FittedBox`` chains (keep inner wrapper)."""
    updated = screen_code
    index = 0
    while True:
        start = updated.find("FittedBox(", index)
        if start == -1:
            break
        paren_start = start + len("FittedBox")
        paren_end = _find_matching_paren(updated, paren_start)
        if paren_end is None:
            break
        block = updated[start : paren_end + 1]
        child_match = re.search(r"child:\s*FittedBox\s*\(", block)
        if child_match is None:
            index = paren_end + 1
            continue
        inner_offset = child_match.start()
        inner_paren = block.find("(", inner_offset)
        if inner_paren == -1:
            index = paren_end + 1
            continue
        inner_end = _find_matching_paren(block, inner_paren)
        if inner_end is None:
            index = paren_end + 1
            continue
        inner_block = block[inner_offset : inner_end + 1]
        updated = updated[:start] + inner_block + updated[paren_end + 1 :]
        index = start + len(inner_block)
    return updated


def _wrap_dart_text_fitted_box(text_widget: str) -> str:
    stripped = text_widget.strip()
    if stripped.startswith("FittedBox("):
        return text_widget
    indent_match = re.match(r"(\s*)", text_widget)
    indent = indent_match.group(1) if indent_match else ""
    inner_indent = f"{indent}  "
    return (
        f"{indent}FittedBox(\n"
        f"{inner_indent}fit: BoxFit.scaleDown,\n"
        f"{inner_indent}child: {stripped},\n"
        f"{indent})"
    )


def _apply_fitted_box_to_multiline_copy_lines(screen_code: str) -> str:
    """Scale down subtitle lines instead of clipping when metrics exceed Figma width."""
    index = 0
    while True:
        column_start = screen_code.find("Column(", index)
        if column_start == -1:
            break
        paren_start = column_start + len("Column")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[column_start : paren_end + 1]
        index = paren_end + 1
        if "mainAxisSize: MainAxisSize.min" not in block:
            continue
        text_matches = list(re.finditer(r"\bText\s*\(", block))
        if len(text_matches) < 2:
            continue
        subtitle_texts: list[tuple[int, int]] = []
        for text_match in text_matches:
            text_start = text_match.start()
            text_paren_start = text_match.end() - 1
            text_paren_end = _find_matching_paren(block, text_paren_start)
            if text_paren_end is None:
                subtitle_texts = []
                break
            text_block = block[text_start : text_paren_end + 1]
            if "softWrap: false" not in text_block:
                continue
            lookback = block[max(0, text_start - 160) : text_start]
            if "FittedBox(" in lookback:
                continue
            subtitle_texts.append((text_start, text_paren_end + 1))
        if len(subtitle_texts) < 2:
            continue
        patched_block = block
        for text_start, text_end in reversed(subtitle_texts):
            text_widget = patched_block[text_start:text_end]
            if text_widget.strip().startswith("FittedBox("):
                continue
            patched_block = (
                patched_block[:text_start]
                + _wrap_dart_text_fitted_box(text_widget)
                + patched_block[text_end:]
            )
        screen_code = (
            screen_code[:column_start] + patched_block + screen_code[paren_end + 1 :]
        )
    return screen_code


def _collapse_rigid_two_line_copy_column(screen_code: str, sanitized_text: str) -> str:
    """Replace legacy two-Text columns (maxLines: 1, softWrap: false) with one multiline Text."""
    if sanitized_text.count("\n") != 1:
        return screen_code
    first_line, second_line = (part.strip() for part in sanitized_text.split("\n", 1))
    if not first_line or not second_line:
        return screen_code
    first_norm = _normalize_text_for_match(first_line)
    second_norm = _normalize_text_for_match(second_line)
    index = 0
    while True:
        column_start = screen_code.find("Column(", index)
        if column_start == -1:
            break
        paren_start = column_start + len("Column")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[column_start : paren_end + 1]
        index = paren_end + 1
        if (
            "mainAxisSize: MainAxisSize.min" not in block
            or block.count("maxLines: 1") < 2
        ):
            continue
        text_matches = list(re.finditer(r"\bText\s*\(", block))
        if len(text_matches) < 2:
            continue
        line_norms: list[str] = []
        style_expr: str | None = None
        align_prefix = ""
        for text_match in text_matches[:2]:
            text_start = text_match.start()
            text_paren_start = text_match.end() - 1
            text_paren_end = _find_matching_paren(block, text_paren_start)
            if text_paren_end is None:
                break
            text_block = block[text_start : text_paren_end + 1]
            quote_body = _first_dart_string_body(text_block) or ""
            line_norms.append(
                _normalize_text_for_match(quote_body, from_dart_literal=True)
            )
            if style_expr is None:
                style_expr = _extract_widget_style_expr(text_block)
                align_match = re.search(r"textAlign:\s*(TextAlign\.\w+)", text_block)
                if align_match is not None:
                    align_prefix = f"textAlign: {align_match.group(1)}, "
        if line_norms != [first_norm, second_norm] or style_expr is None:
            continue
        replacement = _multiline_copy_text_widget(
            sanitized_text=sanitized_text,
            style_expr=style_expr,
            align_prefix=align_prefix,
        )
        return screen_code[:column_start] + replacement + screen_code[paren_end + 1 :]
    return screen_code


def _split_two_line_text_widget(screen_code: str, sanitized_text: str) -> str:
    """Normalize two-line marketing copy to a single multiline Text widget."""
    if sanitized_text.count("\n") != 1:
        return screen_code
    first_line, second_line = (part.strip() for part in sanitized_text.split("\n", 1))
    if not first_line or not second_line:
        return screen_code

    literal = _dart_single_quoted_literal(sanitized_text)
    text_iter = re.finditer(r"\bText\s*\(", screen_code)
    for match in text_iter:
        text_start = match.start()
        paren_start = match.end() - 1
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            continue
        block = screen_code[text_start : paren_end + 1]
        quote_body = _first_dart_string_body(block) or ""
        block_norm = _normalize_text_for_match(quote_body, from_dart_literal=True)
        target_norm = _normalize_text_for_match(sanitized_text)
        first_norm = _normalize_text_for_match(first_line)
        second_norm = _normalize_text_for_match(second_line)
        if block_norm in {first_norm, second_norm}:
            continue
        if block_norm == target_norm and "softWrap: false" in block:
            if "Column(" in screen_code[max(0, text_start - 80) : text_start]:
                continue
            if "\n" in (quote_body or ""):
                continue
        if "maxLines: 1" in block and "softWrap: false" in block:
            continue
        if (
            literal not in block
            and _dart_single_quoted_literal(first_line) not in block
            and block_norm != target_norm
        ):
            continue
        style_expr = _extract_widget_style_expr(block)
        if style_expr is None:
            continue
        align_match = re.search(r"textAlign:\s*(TextAlign\.\w+)", block)
        align_prefix = (
            f"textAlign: {align_match.group(1)}, " if align_match is not None else ""
        )
        replacement = _multiline_copy_text_widget(
            sanitized_text=sanitized_text,
            style_expr=style_expr,
            align_prefix=align_prefix,
        )
        return screen_code[:text_start] + replacement + screen_code[paren_end + 1 :]
    return screen_code


def _patch_multiline_copy_from_tree(
    screen_code: str, clean_tree: CleanDesignTreeNode
) -> str:
    from .positioned import _collect_text_nodes

    updated = screen_code
    for node in _collect_text_nodes(clean_tree):
        if node.type != NodeType.TEXT or node.text_spans:
            continue
        sanitized = sanitize_figma_display_text(node.text or "")
        if "\n" not in sanitized:
            continue
        updated = _collapse_rigid_two_line_copy_column(updated, sanitized)
        updated = _split_two_line_text_widget(updated, sanitized)
    return updated


def _target_text_positioned_height(node: CleanDesignTreeNode) -> float | None:
    """Return a minimum Positioned height when Figma box would clip glyph metrics."""
    if node.type != NodeType.TEXT or node.stack_placement is None:
        return None
    placement_height = node.stack_placement.height
    if placement_height is None:
        return None
    font_size = node.style.font_size
    if font_size is None or font_size <= 0:
        return None
    line_factor = node.style.line_height if node.style.line_height else 1.2
    min_height = font_size * line_factor
    if node.style.glyph_height is not None:
        min_height = max(min_height, node.style.glyph_height + 2.0)
    if placement_height >= min_height * 0.95:
        return None
    return round(min_height + 2.0, 1)


def _figma_multiline_text_frame(node: CleanDesignTreeNode) -> bool:
    """True when the Figma text box is taller than a single line (wrap in Flutter)."""
    if node.type != NodeType.TEXT:
        return False
    if "\n" in (node.text or ""):
        return True
    font_size = node.style.font_size
    if font_size is None or font_size <= 0:
        return False
    line_factor = node.style.line_height if node.style.line_height else 1.2
    placement = node.stack_placement
    if placement is None or placement.height is None:
        return False
    single_line_height = font_size * line_factor
    return float(placement.height) >= single_line_height * 1.35


def _estimated_text_width(node: CleanDesignTreeNode) -> float | None:
    text = (node.text or "").strip()
    font_size = node.style.font_size
    if not text or font_size is None or font_size <= 0:
        return None
    weight = (node.style.font_weight or "").lower()
    weight_scale = 1.12 if weight in {"w700", "w800", "w900", "bold"} else 1.0
    if weight in {"w500", "w600", "medium", "semibold"}:
        weight_scale = 1.05
    per_char = font_size * 0.56 * weight_scale
    letter_spacing = node.style.letter_spacing or 0.0
    width = len(text) * per_char + max(0, len(text) - 1) * letter_spacing
    return round(width + 12.0, 1)


def strip_tight_proportional_leading_in_text_styles(content: str) -> str:
    """Remove proportional leading when ``TextStyle.height`` is below a safe ratio.

    Flutter Web can paint zero-height glyphs when ``TextLeadingDistribution.proportional``
    is paired with a tight line-height factor inside a fixed ``Positioned`` box.
    """
    updated = content
    search_from = 0
    while True:
        match = re.search(r"height:\s*([\d.]+)", updated[search_from:])
        if match is None:
            break
        abs_start = search_from + match.start()
        try:
            ratio = float(match.group(1))
        except ValueError:
            search_from = abs_start + 1
            continue
        if ratio >= _PROPORTIONAL_LEADING_MIN_LINE_HEIGHT or ratio < 0.5:
            search_from = abs_start + match.end() - match.start()
            continue
        if ratio > _LINE_HEIGHT_RATIO_UPPER_BOUND:
            search_from = abs_start + match.end() - match.start()
            continue
        tail_start = search_from + match.end()
        trailing = updated[tail_start : tail_start + 220]
        leading = re.match(
            r"\s*,\s*leadingDistribution:\s*TextLeadingDistribution\.proportional,?",
            trailing,
            re.DOTALL,
        )
        if leading is None:
            search_from = tail_start
            continue
        updated = updated[:tail_start] + updated[tail_start + leading.end() :]
        search_from = abs_start
    return updated


def _node_has_multiline_copy_in_dart_block(block: str) -> bool:
    for _, _, body in _iter_dart_string_literals(block):
        decoded = _decode_dart_string_literal_content(body)
        if "\n" in sanitize_figma_display_text(decoded):
            return True
    if block.count("maxLines: 1") >= 2:
        return True
    return (
        block.count("softWrap: false") >= 2
        and "mainAxisSize: MainAxisSize.min" in block
    )


def apply_clean_tree_text_to_screen(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Replace LLM-paraphrased copy with exact Figma text and tighten headline width."""
    from .controls import (
        _ensure_theme_color_scheme_in_scope,
        _patch_material_buttons_from_tree,
        _patch_secondary_text_below_opaque_fill,
        _patch_stack_filled_buttons_from_tree,
        _patch_theme_wrapped_color_scheme,
    )
    from .positioned import (
        _collect_text_nodes,
        _relax_tight_text_positioned_heights,
        _strip_multiline_copy_positioned_heights,
        _strip_tight_text_positioned_heights,
        _multiline_copy_column_width_from_tree,
        _patch_multiline_copy_column_width,
        expand_text_positioned_widths_from_tree,
        fix_invalid_positioned_constraints,
        fix_positioned_stack_bounds_from_tree,
    )

    updated = screen_code
    for node in sorted(
        _collect_text_nodes(clean_tree),
        key=lambda item: len(item.text or ""),
        reverse=True,
    ):
        figma_text = node.text
        if not figma_text or node.text_spans:
            continue
        literal = _figma_literal(figma_text)
        if literal in updated:
            continue
        normalized = _normalize_text_for_match(figma_text)
        for start, end, candidate in _iter_dart_string_literals(updated):
            candidate_norm = _normalize_text_for_match(
                candidate, from_dart_literal=True
            )
            if not candidate_norm:
                continue
            if candidate_norm == normalized or (
                len(normalized) >= 12
                and (
                    normalized.startswith(candidate_norm)
                    or candidate_norm.startswith(normalized)
                )
            ):
                updated = updated[:start] + literal + updated[end:]
                break

    updated = _patch_richtext_spans_from_tree(updated, clean_tree)
    updated = _patch_multiline_copy_from_tree(updated, clean_tree)
    copy_width = _multiline_copy_column_width_from_tree(clean_tree)
    if copy_width is not None:
        updated = _patch_multiline_copy_column_width(updated, copy_width)
    updated = _strip_multiline_copy_positioned_heights(updated)
    updated = fix_positioned_stack_bounds_from_tree(updated, clean_tree)
    updated = fix_invalid_positioned_constraints(updated)
    updated = _apply_fitted_box_to_multiline_copy_lines(updated)
    updated = _patch_material_buttons_from_tree(updated, clean_tree)
    updated = _patch_stack_filled_buttons_from_tree(updated, clean_tree)
    updated = _patch_secondary_text_below_opaque_fill(updated, clean_tree)
    updated = _relax_tight_text_positioned_heights(updated, clean_tree)
    updated = expand_text_positioned_widths_from_tree(updated, clean_tree)
    updated = _strip_tight_text_positioned_heights(updated)
    updated = _ensure_theme_color_scheme_in_scope(updated)
    updated = _patch_theme_wrapped_color_scheme(updated)
    updated = collapse_nested_fitted_box_wrappers(updated)
    from figma_flutter_agent.generator.dart.file_parts import relocate_directives_to_header

    return relocate_directives_to_header(updated)
