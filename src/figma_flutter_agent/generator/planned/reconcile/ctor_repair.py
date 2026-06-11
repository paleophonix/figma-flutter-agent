"""Constructor repair passes for planned widget files."""

from __future__ import annotations

import re

from loguru import logger

from .ast_helpers import _iter_top_level_brace_inners, _primary_public_widget_class_name

_MAX_WIDGET_CONSTRUCTOR_PARAM_CHARS = 2000


def _widget_constructor_needs_repair(header: str, class_name: str) -> bool:
    """True when the widget header has a known-broken constructor shape."""
    if len(re.findall(rf"\bconst\s+{re.escape(class_name)}\s*\(", header)) > 1:
        return True
    if re.search(rf"\bconst\s+{re.escape(class_name)}\s*\(\s*[^{{\s]", header):
        return True
    if ") : super(key: key" in header or header.count(": super(key: key)") > 1:
        return True
    if re.search(r"Key\?\s+key(?:\s*=\s*null)?\s*,\s*\{", header):
        return True
    if re.search(rf"\bconst\s+{re.escape(class_name)}\s*\(\s*\{{[^}}]*,\s*\{{", header):
        return True
    if re.search(r"\bsuper\.key\b", header) and re.search(r"\bKey\??\s+key\b", header):
        return True
    return header.count("required Key key") > 1


def _constructor_param_identity(segment: str) -> str:
    """Stable key for deduplicating constructor parameter declarations."""
    stripped = segment.strip()
    if stripped.startswith("super.key"):
        return "super.key"
    if re.match(r"(?:required\s+)?Key\??\s+key\b", stripped):
        return "key"
    field = re.match(r"(?:required\s+)?this\.(\w+)", stripped)
    if field is not None:
        return f"this.{field.group(1)}"
    name = re.match(r"([A-Za-z_]\w*)", stripped)
    if name is not None:
        return name.group(1)
    return stripped


def _normalize_widget_constructor_param_segments(params: str) -> list[str]:
    """Collect unique constructor fields from a possibly duplicated LLM param list."""
    from figma_flutter_agent.generator.dart.postprocess import _split_top_level_commas

    params = re.sub(r"(this\.\w+)\s*:\s*(?=['\"(\[\d])", r"\1 = ", params)
    params = re.sub(r"\bvoid\s+onPressed\s*:", "required this.onPressed", params)
    params = re.sub(
        r"\bonPressed\s*:\s*\(\)\s*\{\s*\}",
        "required this.onPressed",
        params,
    )
    params = re.sub(
        r"\bonPressed\s*:\s*[^,]+",
        "required this.onPressed",
        params,
        count=1,
    )
    seen_on_pressed = False
    seen: set[str] = set()
    cleaned: list[str] = []
    for piece in _split_top_level_commas(params):
        segment = piece.strip()
        while segment.startswith("{"):
            segment = segment[1:].lstrip()
        while segment.endswith("}"):
            segment = segment[:-1].rstrip()
        if not segment:
            continue
        if re.search(r"\bonPressed\b", segment):
            if seen_on_pressed:
                continue
            seen_on_pressed = True
            if "required" not in segment and "this.onPressed" not in segment:
                segment = "required this.onPressed"
        if segment in {"{", "}"}:
            continue
        identity = _constructor_param_identity(segment)
        if identity in seen:
            continue
        seen.add(identity)
        cleaned.append(segment)
    has_super_key = any(_constructor_param_identity(segment) == "super.key" for segment in cleaned)
    if has_super_key:
        cleaned = [
            segment
            for segment in cleaned
            if _constructor_param_identity(segment) != "key"
            or segment.strip().startswith("super.key")
        ]
    return cleaned


def _constructor_decl_limit(header: str, search_from: int) -> int:
    build_match = re.search(r"@override\s+Widget\s+build", header[search_from:])
    if build_match is None:
        return len(header)
    return search_from + build_match.start()


def _replace_mangled_widget_constructor(header: str, class_name: str, decl_start: int) -> str:
    """Replace a constructor declaration up to ``;`` (handles nested ``onPressed: () {}``)."""
    from figma_flutter_agent.generator.dart.delimiters import find_balanced_call_close_paren
    from figma_flutter_agent.generator.dart.postprocess import _split_top_level_commas

    decl_limit = _constructor_decl_limit(header, decl_start)
    open_paren = header.find("(", decl_start)
    if open_paren < 0:
        return header
    close_paren = find_balanced_call_close_paren(header, open_paren)
    if close_paren is None:
        decl_region = header[decl_start:decl_limit]
        semi = decl_region.rfind(";")
        if semi < 0:
            return header
        raw = header[open_paren + 1 : decl_start + semi].strip()
        if raw.endswith(")"):
            raw = raw[:-1].rstrip()
        param_inner = raw
        close_paren = decl_start + semi
    else:
        param_inner = header[open_paren + 1 : close_paren]
    if len(param_inner) > _MAX_WIDGET_CONSTRUCTOR_PARAM_CHARS:
        logger.warning(
            "Skipping widget constructor repair for {} ({} param chars)",
            class_name,
            len(param_inner),
        )
        return header
    param_chunks: list[str] = []
    braces_balanced = param_inner.count("{") == param_inner.count("}")
    if not braces_balanced:
        logger.warning(
            "Widget constructor repair for {} uses comma split (unbalanced braces in params)",
            class_name,
        )
    if param_inner.count("required Key key") > 1 or not braces_balanced:
        param_chunks.extend(_split_top_level_commas(param_inner))
        if len(param_chunks) == 1 and param_inner.count("required Key key") > 1:
            flattened = param_inner.replace("{", " ").replace("}", " ")
            param_chunks = _split_top_level_commas(flattened)
    else:
        for inner in _iter_top_level_brace_inners(param_inner):
            param_chunks.extend(_split_top_level_commas(inner))
        if not param_chunks:
            param_chunks.extend(_split_top_level_commas(param_inner))
    normalized = _normalize_widget_constructor_param_segments(", ".join(param_chunks))
    if not normalized:
        return header
    if not any("super.key" in segment for segment in normalized):
        normalized.insert(0, "super.key")
    body = ", ".join(normalized)
    wrapped = f"const {class_name}({{{body}}});"
    decl_region = header[decl_start:decl_limit]
    semi = decl_region.rfind(";")
    if semi < 0:
        decl_end = close_paren + 1
        while decl_end < decl_limit and header[decl_end] in " \t\n\r":
            decl_end += 1
        if decl_end < decl_limit and header[decl_end] == ";":
            decl_end += 1
    else:
        decl_end = decl_start + semi + 1
    tail = header[decl_end:decl_limit] + header[decl_limit:]
    return header[:decl_start] + wrapped + tail


def sync_widget_class_constructors(content: str) -> str:
    """Align the primary widget constructor name with the declared widget class."""
    from figma_flutter_agent.generator.dart.postprocess import repair_obsolete_dart_default_colons

    from .hydrate import _sync_widget_build_class_references

    content = repair_obsolete_dart_default_colons(content)
    class_name = _primary_public_widget_class_name(content)
    if class_name is None:
        return content
    class_match = re.search(
        rf"class\s+{re.escape(class_name)}\s+extends\s+(?:StatelessWidget|StatefulWidget)\b",
        content,
    )
    if class_match is None:
        return content
    class_end = class_match.end()
    build_match = re.search(r"@override\s+Widget\s+build\s*\(", content[class_end:])
    header_end = class_end + build_match.start() if build_match else len(content)
    header = content[class_end:header_end]
    fixed_header = re.sub(
        rf"\bconst\s+(?!{re.escape(class_name)}\b)(\w+)\s*\(",
        f"const {class_name}(",
        header,
        count=1,
    )
    if _widget_constructor_needs_repair(fixed_header, class_name):
        ctor_match = re.search(rf"\bconst\s+{re.escape(class_name)}\s*\(", fixed_header)
        if ctor_match is not None:
            fixed_header = _replace_mangled_widget_constructor(
                fixed_header,
                class_name,
                ctor_match.start(),
            )
    if fixed_header != header:
        content = content[:class_end] + fixed_header + content[header_end:]
    return _sync_widget_build_class_references(content, class_name)
