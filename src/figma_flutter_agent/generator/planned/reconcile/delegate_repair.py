"""Repair passes for delegate and self-referential widget builds."""

from __future__ import annotations

import re

from loguru import logger

_WIDGET_BUILD_HEADER_RE = re.compile(r"@override\s+Widget\s+build\s*\([^)]*\)\s*(?:\{|=>)")
_WIDGET_BUILD_HEADER_FALLBACK_RE = re.compile(r"Widget\s+build\s*\([^)]*\)\s*(?:\{|=>)")

from .class_inspect import (
    _FLUTTER_SDK_WIDGET_CTORS,
    _WIDGET_CTOR_CALL_RE,
    _bare_widget_ctor_return_class,
    _group_paths_by_class,
    _is_cluster_sibling_widget_delegate,
    _is_ctor_self_referential_widget_build,
    _is_foreign_delegate_widget_build,
    _is_self_referential_widget_build,
    _is_shrink_only_widget_source,
    _pick_canonical_widget_path,
    _strip_nested_self_widget_ctors,
    _widget_build_snippet,
    _widget_class_names_by_path,
    _widget_class_paths,
)


def _build_return_expression_site(
    content: str, *, class_name: str | None = None
) -> tuple[int, int] | None:
    """Return ``(expr_start, tail_start)`` for the widget ``build`` body expression."""
    search_from = 0
    search_content = content
    if class_name:
        from .class_inspect import _widget_class_decl_index

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
    refs = [name for name in re.findall(r"\bconst\s+(\w+Widget)\s*\(", build) if name != class_name]
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
    from .class_inspect import _widget_class_build_header_match

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


def _replace_foreign_delegate_build(content: str, class_name: str) -> str:
    """Replace a foreign-delegate ``return`` with ``SizedBox.shrink()`` so subtree refresh runs."""
    if not _is_foreign_delegate_widget_build(content, class_name):
        return content
    return _replace_build_return_expression(content, class_name, "const SizedBox.shrink()")


def _try_inline_foreign_delegate_build(
    content: str,
    class_name: str,
    planned: dict[str, str],
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
                if close_paren is not None and rest[close_paren + 1 :].lstrip().startswith(";"):
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
        abs_start = (
            content.find(build) + context_match.start()
            if build in content
            else context_match.start()
        )
        abs_end = content.find(";", abs_start)
        if abs_end >= 0:
            return content[:abs_start] + "return const SizedBox.shrink();" + content[abs_end + 1 :]
    return content


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
                    target_path = class_paths[name].replace("\\", "/")
                    if target_path != normalized and _bare_widget_ctor_return_class(build) != name:
                        continue
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
            if name in class_paths or _widget_stem_alias_ctor(name, class_name, normalized):
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
            logger.info(
                "Rewrote stale widget ctor name(s) in {}: {}", path, ", ".join(sorted(stale))
            )
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
