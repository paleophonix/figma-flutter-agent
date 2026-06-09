"""AST repair passes for planned Dart files."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from loguru import logger

from .ast_helpers import _iter_top_level_brace_inners, _primary_public_widget_class_name
from .class_inspect import (
    _FLUTTER_SDK_WIDGET_CTORS,
    _WIDGET_CTOR_CALL_RE,
    _bare_widget_ctor_return_class,
    _build_contains_self_widget_ctor,
    _group_paths_by_class,
    _is_cluster_sibling_widget_delegate,
    _is_foreign_delegate_widget_build,
    _is_ctor_self_referential_widget_build,
    _is_self_referential_widget_build,
    _is_shrink_only_widget_source,
    _pick_canonical_widget_path,
    _strip_nested_self_widget_ctors,
    _widget_build_snippet,
    _widget_class_build_header_match,
    _widget_class_decl_index,
    _widget_class_names_by_path,
    _widget_class_paths,
    _planned_has_widget_consumers,
    transitively_referenced_widget_paths,
)
from .hydrate import _sanitize_ingested_widget_source
from .paths import _is_large_planned_dart, planned_content_for_path

_WIDGET_BUILD_HEADER_RE = re.compile(
    r"@override\s+Widget\s+build\s*\([^)]*\)\s*(?:\{|=>)"
)
_WIDGET_BUILD_HEADER_FALLBACK_RE = re.compile(
    r"Widget\s+build\s*\([^)]*\)\s*(?:\{|=>)"
)
_MAX_WIDGET_CONSTRUCTOR_PARAM_CHARS = 2000


def strip_inline_widget_duplicates_from_screen(
    screen_code: str,
    planned_files: Mapping[str, str],
) -> str:
    """Remove widget classes inlined in a screen when ``lib/widgets`` already defines them."""
    from figma_flutter_agent.generator.dart.llm_codegen import _safe_strip_widget_class_definition

    class_paths = _widget_class_paths(dict(planned_files))
    if not class_paths:
        return screen_code

    content = screen_code
    for class_name in sorted(class_paths, key=len, reverse=True):
        if not re.search(
            rf"class\s+{re.escape(class_name)}\s+extends\s+",
            content,
        ):
            continue
        stripped = _safe_strip_widget_class_definition(
            content,
            class_name,
            strip_state=True,
        )
        if stripped == content:
            continue
        logger.info(
            "Removed inline {} from screen (canonical {})",
            class_name,
            class_paths[class_name],
        )
        content = stripped
    return content.rstrip() + ("\n" if screen_code.endswith("\n") else "")


def strip_inline_widget_duplicates_from_screens(planned: dict[str, str]) -> dict[str, str]:
    """Remove widget class bodies inlined in screen files when ``lib/widgets`` owns them."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    updated = dict(planned)
    for path, content in list(planned.items()):
        if not path.endswith("_screen.dart"):
            continue
        patched = strip_inline_widget_duplicates_from_screen(content, planned)
        if patched != content:
            updated[path] = patched
    return updated


def _build_return_expression_site(
    content: str, *, class_name: str | None = None
) -> tuple[int, int] | None:
    """Return ``(expr_start, tail_start)`` for the widget ``build`` body expression."""
    search_from = 0
    search_content = content
    if class_name:
        decl = _widget_class_decl_index(content, class_name)
        if decl is None:
            return None
        search_from = decl
        search_content = content[decl:]

    build_match = _WIDGET_BUILD_HEADER_RE.search(search_content)
    if build_match is None:
        build_match = _WIDGET_BUILD_HEADER_FALLBACK_RE.search(search_content)
    if build_match is None:
        return None
    from figma_flutter_agent.generator.dart.delimiter_expression import find_expression_end

    build_match_start = search_from + build_match.start()
    build_match_end = search_from + build_match.end()
    header = content[build_match_start:build_match_end]
    if header.rstrip().endswith("=>"):
        expr_start = build_match_end
        while expr_start < len(content) and content[expr_start].isspace():
            expr_start += 1
        expr_end = find_expression_end(content, expr_start)
        if expr_end is None:
            semi = content.find(";", expr_start)
            if semi < 0:
                return None
            return expr_start, semi + 1
        tail_start = expr_end
        if tail_start < len(content) and content[tail_start] == ";":
            tail_start += 1
        return expr_start, tail_start

    body = content[build_match_end:]
    ret = re.search(r"\breturn\b", body)
    if ret is None:
        return None
    expr_start = build_match_end + ret.end()
    expr_end = find_expression_end(content, expr_start)
    if expr_end is None:
        semi = content.find(";", expr_start)
        if semi < 0:
            return None
        return expr_start, semi + 1
    tail_start = expr_end
    if tail_start < len(content) and content[tail_start] == ";":
        tail_start += 1
    return expr_start, tail_start


def _extract_build_return_expression(content: str, class_name: str) -> str | None:
    if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", content):
        return None
    site = _build_return_expression_site(content, class_name=class_name)
    if site is None:
        return None
    expr_start, expr_end = site
    return content[expr_start:expr_end].strip()


def _foreign_delegate_target_class(build: str, class_name: str) -> str | None:
    bare = _bare_widget_ctor_return_class(build)
    if bare and bare not in (class_name, "__context_widget__") and bare.endswith("Widget"):
        return bare
    refs = [
        name
        for name in re.findall(r"\bconst\s+(\w+Widget)\s*\(", build)
        if name != class_name
    ]
    if len(refs) == 1:
        return refs[0]
    return None


def _widget_body_is_inlinable_target(content: str, class_name: str) -> bool:
    if not content.strip():
        return False
    if _is_shrink_only_widget_source(content):
        return False
    if _is_self_referential_widget_build(content, class_name):
        return False
    return not _is_foreign_delegate_widget_build(content, class_name)


def _replace_build_return_expression(content: str, class_name: str, replacement_expr: str) -> str:
    site = _build_return_expression_site(content, class_name=class_name)
    if site is None:
        return content
    expr_start, tail_start = site
    header_site = _widget_class_build_header_match(content, class_name)
    if header_site is None:
        return content
    build_match_start, build_match_end, header = header_site
    if header.rstrip().endswith("=>"):
        return content[:build_match_end] + f" {replacement_expr};" + content[tail_start:]
    body = content[build_match_end:expr_start]
    ret = re.search(r"\breturn\b", body)
    if ret is None:
        return content
    stmt_start = build_match_end + ret.start()
    return content[:stmt_start] + f"return {replacement_expr};" + content[tail_start:]


def _try_inline_foreign_delegate_build(
    content: str,
    class_name: str,
    planned: Mapping[str, str],
) -> str | None:
    if not _is_foreign_delegate_widget_build(content, class_name):
        return None
    build = _widget_build_snippet(content, class_name=class_name, max_chars=4000)
    target_class = _foreign_delegate_target_class(build, class_name)
    if target_class is None:
        return None
    class_paths = _widget_class_paths(planned)
    target_path = class_paths.get(target_class)
    if target_path is None:
        return None
    target_content = planned.get(target_path, "")
    if not _widget_body_is_inlinable_target(target_content, target_class):
        return None
    target_expr = _extract_build_return_expression(target_content, target_class)
    if not target_expr:
        return None
    inlined = _replace_build_return_expression(content, class_name, target_expr)
    if inlined == content:
        return None
    return inlined


def _replace_foreign_delegate_build(content: str, class_name: str) -> str:
    """Replace a foreign-delegate ``return`` with ``SizedBox.shrink()`` so subtree refresh runs."""
    if not _is_foreign_delegate_widget_build(content, class_name):
        return content
    return _replace_build_return_expression(content, class_name, "const SizedBox.shrink()")


def repair_stale_widget_ctor_names_in_planned(planned: dict[str, str]) -> dict[str, str]:
    """Rewrite ``build`` calls to missing or mismatched widget classes onto the declared file class."""
    from .class_inspect import _widget_stem_alias_ctor

    class_paths = _widget_class_paths(planned)
    updated = dict(planned)
    for path, class_name in _widget_class_names_by_path(planned).items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/"):
            continue
        content = updated.get(path, "")
        build = _widget_build_snippet(content, class_name=class_name, max_chars=8000)
        stale: set[str] = set()
        for match in _WIDGET_CTOR_CALL_RE.finditer(build):
            name = match.group(1)
            if name in _FLUTTER_SDK_WIDGET_CTORS or name == class_name:
                continue
            if not name.endswith("Widget"):
                continue
            if name in class_paths:
                if name != class_name and not _is_cluster_sibling_widget_delegate(class_name, name):
                    stale.add(name)
                continue
            stale.add(name)
        if not stale:
            continue
        build_match = re.search(r"@override\s+Widget\s+build\s*\(", content)
        if build_match is None:
            continue
        build_start = build_match.start()
        header = content[:build_start]
        build_body = content[build_start:]
        patched_build = build_body
        for name in stale:
            if name in class_paths:
                replacement = class_name
            elif _widget_stem_alias_ctor(name, class_name, normalized):
                replacement = class_name
            else:
                replacement = "SizedBox.shrink"
            patched_build = re.sub(
                rf"\b{re.escape(name)}\s*\(",
                f"{replacement}(",
                patched_build,
            )
        patched = header + patched_build
        if patched != content:
            logger.info("Rewrote stale widget ctor name(s) in {}: {}", path, ", ".join(sorted(stale)))
            updated[path] = patched
    return updated


def repair_foreign_delegate_widget_builds(planned: dict[str, str]) -> dict[str, str]:
    """Inline or shrink widgets whose ``build`` only forwards to another widget class."""
    updated = dict(planned)
    for _ in range(6):
        changed = False
        for path, class_name in _widget_class_names_by_path(updated).items():
            content = updated.get(path, "")
            if not _is_foreign_delegate_widget_build(content, class_name):
                continue
            if _is_self_referential_widget_build(content, class_name):
                continue
            inlined = _try_inline_foreign_delegate_build(content, class_name, updated)
            if inlined is not None:
                logger.info("Inlined foreign delegate widget build: {}", path)
                updated[path] = inlined
                changed = True
                continue
            patched = _replace_foreign_delegate_build(content, class_name)
            if patched != content:
                logger.info("Shrunk foreign delegate widget build: {}", path)
                updated[path] = patched
                changed = True
        if not changed:
            break
    return updated


def _replace_self_referential_build(content: str, class_name: str) -> str:
    build = _widget_build_snippet(content, class_name=class_name, max_chars=4000)
    return_match = re.search(r"\breturn\b", build)
    if return_match is not None:
        rest = build[return_match.end() :].lstrip()
        if rest.startswith("const "):
            rest = rest[6:].lstrip()
        if rest.startswith(class_name):
            open_paren = rest.find("(", len(class_name))
            if open_paren >= 0:
                from figma_flutter_agent.generator.dart.delimiters import (
                    find_balanced_call_close_paren,
                )

                close_paren = find_balanced_call_close_paren(rest, open_paren)
                if close_paren is not None and rest[close_paren + 1 :].lstrip().startswith(
                    ";"
                ):
                    abs_start = (
                        content.find(build) + return_match.start()
                        if build in content
                        else return_match.start()
                    )
                    abs_end = content.find(";", abs_start)
                    if abs_end >= 0:
                        return (
                            content[:abs_start]
                            + "return const SizedBox.shrink();"
                            + content[abs_end + 1 :]
                        )
    context_match = re.search(r"return\s+context\.widget\s*;", build)
    if context_match is not None:
        abs_start = content.find(build) + context_match.start() if build in content else context_match.start()
        abs_end = content.find(";", abs_start)
        if abs_end >= 0:
            return (
                content[:abs_start]
                + "return const SizedBox.shrink();"
                + content[abs_end + 1 :]
            )
    return content


def repair_self_referential_widget_builds(planned: dict[str, str]) -> dict[str, str]:
    """Drop widget files whose ``build`` only instantiates self or another widget class."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    def _is_stub_build(content: str, class_name: str) -> bool:
        return _is_self_referential_widget_build(
            content, class_name
        ) or _is_foreign_delegate_widget_build(content, class_name)

    updated = dict(planned)
    for class_name, paths in _group_paths_by_class(planned).items():
        if len(paths) < 2:
            continue
        canonical = _pick_canonical_widget_path(paths, updated)
        for path in paths:
            if path == canonical:
                continue
            content = updated.get(path, "")
            if _is_stub_build(content, class_name):
                updated.pop(path, None)
    for class_name, paths in _group_paths_by_class(updated).items():
        if len(paths) != 1:
            continue
        path = paths[0]
        content = updated.get(path, "")
        if not _is_ctor_self_referential_widget_build(content, class_name):
            continue
        patched = _replace_self_referential_build(content, class_name)
        if patched != content:
            logger.info("Replaced ctor self-referential widget build: {}", path)
            updated[path] = patched
    for path, class_name in _widget_class_names_by_path(updated).items():
        content = updated.get(path, "")
        patched = _strip_nested_self_widget_ctors(content, class_name)
        if patched != content:
            logger.info("Stripped nested self widget ctor(s): {}", path)
            updated[path] = patched
    return updated


def prune_duplicate_widget_classes(planned: dict[str, str]) -> dict[str, str]:
    """Drop duplicate widget files that redeclare the same public widget class."""
    by_class: dict[str, list[str]] = {}
    for path, class_name in _widget_class_names_by_path(planned).items():
        by_class.setdefault(class_name, []).append(path)

    drop_paths: set[str] = set()
    for paths in by_class.values():
        if len(paths) < 2:
            continue
        canonical = _pick_canonical_widget_path(paths, planned)
        drop_paths.update(path for path in paths if path != canonical)

    if not drop_paths:
        return planned

    updated = dict(planned)
    for path in drop_paths:
        updated.pop(path, None)
    return updated


def prune_unreferenced_planned_widgets(planned: dict[str, str]) -> dict[str, str]:
    """Drop ``lib/widgets`` files not referenced from layout, screens, or other widgets."""
    if not _planned_has_widget_consumers(planned):
        return planned
    referenced = transitively_referenced_widget_paths(planned)
    updated = dict(planned)
    for path in list(updated.keys()):
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/") or not normalized.endswith(".dart"):
            continue
        if path in referenced:
            continue
        updated.pop(path, None)
        logger.info("Pruned unreferenced planned widget: {}", normalized)
    return updated


def drop_unparseable_planned_widget_files(planned: dict[str, str]) -> dict[str, str]:
    """Remove or repair ``lib/widgets`` bodies that fail delimiter validation after sanitize."""
    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        validate_dart_delimiters,
    )

    has_consumers = _planned_has_widget_consumers(planned)
    referenced = transitively_referenced_widget_paths(planned) if has_consumers else set()
    updated = dict(planned)
    for path, content in list(updated.items()):
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/") or not normalized.endswith(".dart"):
            continue
        sanitized = _sanitize_ingested_widget_source(content, widget_path=normalized)
        if validate_dart_delimiters(sanitized) is None:
            if sanitized != content:
                updated[path] = sanitized
            continue
        if has_consumers and path not in referenced:
            updated.pop(path, None)
            logger.warning(
                "Dropped unparseable unreferenced planned widget: {}",
                normalized,
            )
            continue
        repaired = repair_dart_delimiters(sanitized)
        if validate_dart_delimiters(repaired) is None:
            updated[path] = repaired
            logger.info("Repaired delimiter damage in referenced widget: {}", normalized)
            continue
        logger.warning(
            "Referenced planned widget still unparseable after repair: {}",
            normalized,
        )
    return updated


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


def repair_planned_misplaced_text_style_params(
    planned: dict[str, str],
    analyze_errors: tuple[str, ...] | list[str] = (),
) -> dict[str, str]:
    """Wrap ``Text(fontSize: …)`` mistakes (with or without a partial ``style:``)."""
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        wrap_misplaced_text_style_params_on_text,
    )

    style_param_errors = (
        "fontSize' isn't defined",
        "fontWeight' isn't defined",
        "letterSpacing' isn't defined",
        "fontFamilyFallback' isn't defined",
    )
    force_all = not analyze_errors or any(
        any(token in error for token in style_param_errors) for error in analyze_errors
    )
    if not force_all:
        return planned

    updated = dict(planned)
    for path, content in planned.items():
        if not path.endswith(".dart"):
            continue
        repaired = wrap_misplaced_text_style_params_on_text(content)
        if repaired != content:
            updated[path] = repaired
    return updated


def sanitize_screen_emit_syntax(content: str) -> str:
    """Repair common screen emit issues (misplaced TextStyle params, delimiters)."""
    from figma_flutter_agent.generator.dart.postprocess import inline_orphan_text_scaler_refs
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        apply_planned_delimiter_balance,
        fix_children_list_orphan_text_scaler,
        fix_garbage_closers_after_link_rich,
        fix_text_align_comma_semicolon,
        wrap_misplaced_text_style_params_on_text,
    )

    content = fix_garbage_closers_after_link_rich(content)
    content = fix_children_list_orphan_text_scaler(content)
    content = fix_text_align_comma_semicolon(content)
    content = inline_orphan_text_scaler_refs(content)
    content = wrap_misplaced_text_style_params_on_text(content)
    return apply_planned_delimiter_balance(content, force=True)


def _sanitize_screen_dart_syntax(content: str) -> str:
    """Repair delimiter drift on screen files via the AST sidecar."""
    return sanitize_screen_emit_syntax(content)


def _sanitize_widget_dart_syntax(content: str) -> str:
    from figma_flutter_agent.generator.dart.syntax_repairs import sanitize_planned_widget_syntax

    return sanitize_planned_widget_syntax(content)


def _sanitize_planned_dart_syntax(path: str, content: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.endswith("_screen.dart"):
        return _sanitize_screen_dart_syntax(content)
    if normalized.startswith("lib/widgets/") and normalized.endswith(".dart"):
        return _sanitize_widget_dart_syntax(content)
    return content


def _balance_planned_widget_delimiters(planned: dict[str, str]) -> dict[str, str]:
    """Repair delimiter drift on feature screens and extracted widget files."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        apply_planned_delimiter_balance,
        sanitize_planned_widget_syntax,
    )

    updated = dict(planned)
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        is_screen = normalized.startswith("lib/features/") and normalized.endswith(
            "_screen.dart"
        )
        is_widget = normalized.startswith("lib/widgets/") and normalized.endswith(".dart")
        if not is_screen and not is_widget:
            continue
        if validate_dart_delimiters(content) is None:
            continue
        repaired = (
            sanitize_planned_widget_syntax(content)
            if is_widget
            else apply_planned_delimiter_balance(content)
        )
        if repaired != content:
            updated[path] = repaired
    return updated


def repair_planned_format_parse_failures(
    planned: dict[str, str],
    format_paths: tuple[str, ...],
    *,
    analyze_errors: tuple[str, ...] = (),
    repair_pass: int = 0,
) -> dict[str, str]:
    """Deterministic cleanup when ``dart format`` cannot parse planned Dart (e.g. ``])))}}``)."""
    if not format_paths:
        return planned
    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        trim_surplus_dart_delimiters,
        validate_dart_delimiters,
    )
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        append_missing_closers_on_lines,
        apply_format_parse_error_insertions,
        apply_planned_delimiter_balance,
        is_garbage_closer_only_line,
        is_orphan_semicolon_line,
        parse_format_error_line_numbers,
        sanitize_planned_widget_syntax,
    )

    def _format_errors_suggest_delimiters() -> bool:
        tokens = (
            "Expected to find ']'",
            "Expected to find '}'",
            "Expected to find ')'",
            "Expected to find ','",
            "Expected to find ';'",
        )
        return any(any(token in error for token in tokens) for error in analyze_errors)

    def _repair_format_parse_source(text: str, *, normalized_path: str) -> str:
        if analyze_errors:
            text = apply_format_parse_error_insertions(
                text,
                analyze_errors,
                attempt=repair_pass,
            )
        if error_lines:
            text = append_missing_closers_on_lines(text, error_lines)
        trimmed = trim_surplus_dart_delimiters(text)
        if trimmed is not None:
            text = trimmed
        if normalized_path.endswith("_screen.dart") or (
            _format_errors_suggest_delimiters()
            and normalized_path.startswith("lib/widgets/")
            and normalized_path.endswith(".dart")
        ):
            text = sanitize_screen_emit_syntax(text)
        text = repair_dart_delimiters(text)
        if validate_dart_delimiters(text) is not None:
            text = apply_planned_delimiter_balance(text, force=True)
            text = repair_dart_delimiters(text)
        return repair_dart_delimiters(text)

    error_lines = parse_format_error_line_numbers(analyze_errors)
    for path in format_paths:
        located = planned_content_for_path(planned, path)
        if located is None:
            continue
        normalized, content = located
        lines = content.splitlines()
        if error_lines:
            for line_no in error_lines:
                index = line_no - 1
                if 0 <= index < len(lines) and (
                    is_garbage_closer_only_line(lines[index])
                    or is_orphan_semicolon_line(lines[index])
                ):
                    lines[index] = ""
            text = "\n".join(lines)
        else:
            text = content
        repaired = _repair_format_parse_source(text, normalized_path=normalized)
        if normalized.startswith("lib/widgets/") and normalized.endswith(".dart"):
            repaired = sanitize_planned_widget_syntax(repaired)
        if repaired != content:
            planned[normalized] = repaired
            for key in list(planned):
                if key != normalized and key.replace("\\", "/") == normalized:
                    del planned[key]
    return planned
