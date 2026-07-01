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
    from .class_inspect import _single_foreign_widget_delegate_target

    return _single_foreign_widget_delegate_target(build, class_name)


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
    from .class_inspect import _host_has_structural_chrome

    if _host_has_structural_chrome(build, class_name):
        return None
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
    """Rewrite widget ctor calls that reference missing or mismatched ``lib/widgets`` classes."""
    from .class_inspect import _widget_stem_alias_ctor
    from .imports import _consumer_paths_needing_widget_imports

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

    for path, content in list(updated.items()):
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart") or not _consumer_paths_needing_widget_imports(
            normalized
        ):
            continue
        if normalized.startswith("lib/widgets/"):
            continue
        stale_names: set[str] = set()
        for match in _WIDGET_CTOR_CALL_RE.finditer(content):
            name = match.group(1)
            if name in _FLUTTER_SDK_WIDGET_CTORS or not name.endswith("Widget"):
                continue
            if name not in class_paths:
                stale_names.add(name)
        if not stale_names:
            continue
        patched = content
        for name in sorted(stale_names, key=len, reverse=True):
            patched = re.sub(
                rf"\b{re.escape(name)}\s*\(",
                "SizedBox.shrink(",
                patched,
            )
        if patched != content:
            logger.info(
                "Rewrote stale widget ctor name(s) in consumer {}: {}",
                normalized,
                ", ".join(sorted(stale_names)),
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


def _widget_foreign_delegate_target(content: str, class_name: str) -> str | None:
    build = _widget_build_snippet(content, class_name=class_name, max_chars=4000)
    return _foreign_delegate_target_class(build, class_name)


def _find_delegate_cycles(planned: dict[str, str]) -> list[list[str]]:
    """Return class-name cycles in the foreign-widget delegate graph."""
    class_paths = _widget_class_paths(planned)
    graph: dict[str, str] = {}
    for path, class_name in _widget_class_names_by_path(planned).items():
        content = planned.get(path, "")
        if not _is_foreign_delegate_widget_build(content, class_name):
            continue
        target = _widget_foreign_delegate_target(content, class_name)
        if target is None or target not in class_paths:
            continue
        graph[class_name] = target

    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(node: str) -> None:
        if node in stack:
            cycle_start = node
            cycle = [node]
            cursor = graph.get(node)
            while cursor is not None and cursor != cycle_start:
                cycle.append(cursor)
                cursor = graph.get(cursor)
            if cursor == cycle_start:
                cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        stack.add(node)
        target = graph.get(node)
        if target is not None:
            dfs(target)
        stack.remove(node)

    for class_name in graph:
        dfs(class_name)
    return cycles


def repair_mutual_delegate_widget_cycles(planned: dict[str, str]) -> dict[str, str]:
    """Break acyclic violations in extracted-widget delegate graphs before write."""
    updated = dict(planned)
    for _ in range(8):
        cycles = _find_delegate_cycles(updated)
        if not cycles:
            break
        changed = False
        broken: set[str] = set()
        for cycle in cycles:
            for break_class in cycle:
                if break_class in broken:
                    continue
                paths = [
                    path
                    for path, name in _widget_class_names_by_path(updated).items()
                    if name == break_class
                ]
                if not paths:
                    continue
                path = paths[0]
                content = updated.get(path, "")
                patched = _replace_foreign_delegate_build(content, break_class)
                if patched == content:
                    patched = _replace_self_referential_build(content, break_class)
                if patched != content:
                    logger.info("Broke delegate widget cycle via {} in {}", break_class, cycle)
                    updated[path] = patched
                    broken.add(break_class)
                    changed = True
        if not changed:
            break
    return updated


def repair_self_referential_widget_builds(planned: dict[str, str]) -> dict[str, str]:
    """Drop widget files whose ``build`` only instantiates self or another widget class."""
    updated = repair_mutual_delegate_widget_cycles(planned)
    class_paths = _widget_class_paths(updated)
    if not class_paths:
        return updated

    def _is_stub_build(content: str, class_name: str) -> bool:
        return _is_self_referential_widget_build(
            content, class_name
        ) or _is_foreign_delegate_widget_build(content, class_name)

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
