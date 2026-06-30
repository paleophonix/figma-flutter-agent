"""Widget class analysis."""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from .ast_helpers import (
    _primary_public_widget_class_name,
)
from .paths import (
    _normalized_widget_stem,
    preferred_widget_path_for_class,
)

_CLUSTER_VARIANT_PARAMS = ("isForward", "label", "isSelected")
_CLUSTER_GROUP_WIDGET_STEM_RE = re.compile(r"^group\d+", re.IGNORECASE)
_WIDGET_CLASS_RE = re.compile(
    r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)
_WIDGET_BUILD_HEADER_RE = re.compile(r"@override\s+Widget\s+build\s*\([^)]*\)\s*(?:\{|=>)")
_WIDGET_BUILD_HEADER_FALLBACK_RE = re.compile(r"Widget\s+build\s*\([^)]*\)\s*(?:\{|=>)")
_WIDGET_USE_RE = re.compile(r"\b(\w+Widget)\s*\(")
_WIDGET_CTOR_CALL_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*Widget\d*)\s*\(")
_FLUTTER_SDK_WIDGET_CTORS = frozenset(
    {
        "StatelessWidget",
        "StatefulWidget",
        "State",
        "Widget",
        "InheritedWidget",
        "RenderObjectWidget",
    }
)


def _widget_class_decl_index(content: str, class_name: str) -> int | None:
    match = re.search(rf"\bclass\s+{re.escape(class_name)}\s+extends\b", content)
    return match.start() if match else None


def _widget_class_build_header_match(content: str, class_name: str) -> tuple[int, int, str] | None:
    """Return ``(abs_start, abs_end, header_text)`` for the class ``build`` method header."""
    decl = _widget_class_decl_index(content, class_name)
    if decl is None:
        return None
    scope = content[decl:]
    match = _WIDGET_BUILD_HEADER_RE.search(scope)
    if match is None:
        match = _WIDGET_BUILD_HEADER_FALLBACK_RE.search(scope)
    if match is None:
        return None
    return decl + match.start(), decl + match.end(), match.group(0)


def _widget_class_build_bounds(content: str, class_name: str) -> tuple[int, int] | None:
    """Return absolute ``(start, end)`` span of the hosting widget ``build`` method."""
    header_site = _widget_class_build_header_match(content, class_name)
    if header_site is None:
        return None
    abs_start, abs_hdr_end, header = header_site
    from figma_flutter_agent.generator.dart.delimiter_expression import find_expression_end

    if header.rstrip().endswith("=>"):
        expr_start = abs_hdr_end
        while expr_start < len(content) and content[expr_start].isspace():
            expr_start += 1
        expr_end = find_expression_end(content, expr_start)
        if expr_end is None:
            semi = content.find(";", expr_start)
            if semi < 0:
                return None
            return abs_start, semi + 1
        tail = expr_end
        if tail < len(content) and content[tail] == ";":
            tail += 1
        return abs_start, tail

    open_brace = abs_hdr_end - 1
    depth = 0
    for i in range(open_brace, len(content)):
        ch = content[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return abs_start, i + 1
    return None


def _widget_build_snippet(
    content: str, *, class_name: str | None = None, max_chars: int = 1200
) -> str:
    if class_name:
        decl = _widget_class_decl_index(content, class_name)
        if decl is not None:
            scope = content[decl:]
            match = re.search(r"@override\s+Widget\s+build\s*\([^)]*\)", scope)
            if match is None:
                match = re.search(r"Widget\s+build\s*\([^)]*\)", scope)
            if match is not None:
                start = decl + match.end()
                return content[start : start + max_chars]
    match = re.search(r"@override\s+Widget\s+build\s*\([^)]*\)", content)
    if match is None:
        match = re.search(r"Widget\s+build\s*\([^)]*\)", content)
    if match is None:
        return content[:max_chars]
    start = match.end()
    return content[start : start + max_chars]


def _bare_widget_ctor_return_class(build: str) -> str | None:
    """Return the widget class name when ``build`` is only ``return const Foo();``."""
    if re.search(r"return\s+context\.widget\b", build):
        return "__context_widget__"
    return_match = re.search(r"(?:\breturn\b|=>)\s*", build)
    if return_match is None:
        return None
    rest = build[return_match.end() :].lstrip()
    if rest.startswith("const "):
        rest = rest[6:].lstrip()
    ctor_match = re.match(r"(\w+)\s*\(", rest)
    if ctor_match is None:
        return None
    called = ctor_match.group(1)
    open_paren = rest.find("(", len(called))
    if open_paren < 0:
        return None
    from figma_flutter_agent.generator.dart.delimiters import find_balanced_call_close_paren

    close_paren = find_balanced_call_close_paren(rest, open_paren)
    if close_paren is None:
        return None
    after = rest[close_paren + 1 :].lstrip()
    if not after.startswith(";"):
        return None
    return called


def _widget_stem_alias_ctor(ctor_name: str, class_name: str, widget_path: str) -> bool:
    """True when ``ctor_name`` is a numbered/stem alias of the file's declared widget class."""
    from figma_flutter_agent.generator.layout.common import to_pascal_case

    if ctor_name == class_name:
        return False
    stem = to_pascal_case(Path(widget_path).stem)
    ctor_base = ctor_name.removesuffix("Widget")
    if ctor_base and (
        ctor_base in {stem, class_name}
        or stem.endswith(ctor_base)
        or class_name.endswith(ctor_base)
    ):
        return True
    ctor_root = ctor_name.rstrip("0123456789")
    class_root = class_name.rstrip("0123456789")
    return (
        ctor_name.startswith(class_root)
        or class_name.startswith(ctor_root)
        or ctor_root == class_root
    )


def _build_contains_self_widget_ctor(content: str, class_name: str) -> bool:
    """True when ``build`` instantiates the hosting widget class (directly or nested)."""
    build = _widget_build_snippet(content, class_name=class_name, max_chars=8000)
    return bool(re.search(rf"\b(?:const\s+)?{re.escape(class_name)}\s*\(", build))


def _strip_would_collapse_substantive_widget(build_body: str, patched_build: str) -> bool:
    """True when stripping nested self ctors would erase real subtree content."""
    if patched_build == build_body or "SizedBox.shrink" not in patched_build:
        return False
    return (
        "SvgPicture.asset" in build_body
        or "Image.asset" in build_body
        or ("Stack(" in build_body and "Positioned(" in build_body)
        or "BoxDecoration(" in build_body
        or "Material(" in build_body
        or "Ink(" in build_body
        or "RepaintBoundary(" in build_body
    )


def _strip_nested_self_widget_ctors(content: str, class_name: str) -> str:
    """Replace nested ``ClassName()`` calls inside the hosting widget ``build``."""
    if not _build_contains_self_widget_ctor(content, class_name):
        return content
    bounds = _widget_class_build_bounds(content, class_name)
    if bounds is None:
        return content
    start, end = bounds
    build_body = content[start:end]
    patched_build = re.sub(
        rf"\bconst\s+{re.escape(class_name)}\s*\([^)]*\)",
        "const SizedBox.shrink()",
        build_body,
    )
    patched_build = re.sub(
        rf"\b{re.escape(class_name)}\s*\(",
        "SizedBox.shrink(",
        patched_build,
    )
    if _strip_would_collapse_substantive_widget(build_body, patched_build):
        return content
    return content[:start] + patched_build + content[end:]


def _is_self_referential_widget_build(content: str, class_name: str) -> bool:
    if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", content):
        return False
    build = _widget_build_snippet(content, class_name=class_name)
    called = _bare_widget_ctor_return_class(build)
    if called == "__context_widget__":
        return True
    return called == class_name


def _single_foreign_widget_delegate_target(build: str, class_name: str) -> str | None:
    """Return a sole extracted-widget ctor target referenced from a thin delegate build."""
    bare = _bare_widget_ctor_return_class(build)
    if (
        bare
        and bare not in (class_name, "__context_widget__", "SizedBox")
        and bare.endswith("Widget")
    ):
        return bare
    refs = [name for name in re.findall(r"\bconst\s+(\w+Widget)\s*\(", build) if name != class_name]
    if len(refs) == 1:
        return refs[0]
    return None


def _host_has_structural_chrome(build: str, class_name: str) -> bool:
    """True when ``build`` hosts real layout chrome plus a foreign widget reference."""
    bare = _bare_widget_ctor_return_class(build)
    if (
        bare
        and bare.endswith("Widget")
        and bare not in (class_name, "__context_widget__", "SizedBox")
    ):
        return False
    chrome_markers = (
        "Container(",
        "Row(",
        "Column(",
        "Expanded(",
        "ClipRRect(",
        "BoxDecoration",
        "DecoratedBox(",
    )
    if not any(marker in build for marker in chrome_markers):
        return False
    foreign_refs = [
        name for name in re.findall(r"\bconst\s+(\w+Widget)\s*\(", build) if name != class_name
    ]
    return bool(foreign_refs)


def _is_foreign_delegate_widget_build(content: str, class_name: str) -> bool:
    """``build`` only forwards to another widget class (wrong or stale subtree body)."""
    if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", content):
        return False
    build = _widget_build_snippet(content, class_name=class_name, max_chars=4000)
    if "SvgPicture.asset" in build or "Image.asset" in build:
        return False
    if _host_has_structural_chrome(build, class_name):
        return False
    if _single_foreign_widget_delegate_target(build, class_name) is not None:
        return True
    called = _bare_widget_ctor_return_class(build)
    if (
        called not in (None, "__context_widget__")
        and called != class_name
        and called.endswith("Widget")
    ):
        return True
    if "Stack(" not in build and "Positioned(" not in build:
        return False
    if "Container(" in build or "BoxDecoration" in build or "DecoratedBox" in build:
        return False
    foreign = [
        name for name in re.findall(r"\bconst\s+(\w+Widget)\s*\(", build) if name != class_name
    ]
    return bool(foreign)


def _is_cluster_sibling_widget_delegate(declared_class: str, target_class: str) -> bool:
    """``Group6779Widget`` forwarding to ``Group6777Widget`` — re-render, not ctor rename."""
    from figma_flutter_agent.generator.layout.common import to_snake_case

    a = to_snake_case(declared_class)
    b = to_snake_case(target_class)
    return bool(_CLUSTER_GROUP_WIDGET_STEM_RE.match(a) and _CLUSTER_GROUP_WIDGET_STEM_RE.match(b))


def _pick_canonical_widget_path(paths: list[str], planned: dict[str, str]) -> str:
    def sort_key(path: str) -> tuple[int, int, int, str]:
        content = planned.get(path, "")
        class_name = _primary_public_widget_class_name(content) or ""
        self_ref_rank = (
            1
            if _is_self_referential_widget_build(content, class_name)
            or _is_foreign_delegate_widget_build(content, class_name)
            else 0
        )
        shrink_rank = 1 if _is_shrink_only_widget_source(content) else 0
        stem = Path(path).stem
        from figma_flutter_agent.generator.layout.common import to_snake_case

        expected_stem = to_snake_case(class_name) if class_name else stem
        stem_match_rank = 0 if _normalized_widget_stem(stem) == expected_stem else 1
        suffix_match = re.search(r"_(\d+)$", stem)
        suffix_rank = int(suffix_match.group(1)) if suffix_match else 0
        return (self_ref_rank, shrink_rank, stem_match_rank, -len(content), suffix_rank, path)

    return sorted(paths, key=sort_key)[0]


def _is_shrink_only_widget_source(content: str) -> bool:
    if "SvgPicture.asset" in content or "Image.asset" in content:
        return False
    build = _widget_build_snippet(content)
    if "Stack(" in build or "Positioned(" in build:
        return False
    return bool(
        re.search(r"return\s+const\s+SizedBox\.shrink\(\)\s*;", build)
        or re.search(r"=>\s*const\s+SizedBox\.shrink\(\)\s*;", build)
        or re.search(
            r"(?:return|=>)\s+SizedBox\([^)]*child:\s*const\s+SizedBox\.shrink\(\)\s*\)\s*;?",
            build,
        )
        or "RepaintBoundary(child: const SizedBox.shrink())" in build
    )


def _widget_class_names_by_path(planned: dict[str, str]) -> dict[str, str]:
    class_names: dict[str, str] = {}
    for path, content in planned.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _primary_public_widget_class_name(content)
        if class_name is None:
            continue
        class_names[path] = class_name
    return class_names


def _group_paths_by_class(planned: dict[str, str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path, class_name in _widget_class_names_by_path(planned).items():
        grouped.setdefault(class_name, []).append(path)
    return grouped


def _widget_class_paths(planned: dict[str, str]) -> dict[str, str]:
    grouped = _group_paths_by_class(planned)
    class_paths: dict[str, str] = {}
    for class_name, paths in grouped.items():
        preferred = preferred_widget_path_for_class(class_name)
        if preferred in planned:
            class_paths[class_name] = preferred
        elif len(paths) == 1:
            class_paths[class_name] = paths[0]
        else:
            class_paths[class_name] = _pick_canonical_widget_path(paths, planned)
    return class_paths


def _widget_path_for_ctor_name(planned: dict[str, str], ctor_name: str) -> str | None:
    """Resolve a consumer ``FooWidget()`` call to a planned ``lib/widgets`` path."""
    class_paths = _widget_class_paths(planned)
    if ctor_name in class_paths:
        return class_paths[ctor_name]
    preferred = preferred_widget_path_for_class(ctor_name).replace("\\", "/")
    if preferred in planned:
        return preferred
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/") or not normalized.endswith(".dart"):
            continue
        declared = _primary_public_widget_class_name(content)
        if declared == ctor_name:
            return normalized
    return None


def _collect_widget_use_class_names(
    source: str,
    known_class_names: frozenset[str] | set[str] = frozenset(),
) -> set[str]:
    names = set(_WIDGET_USE_RE.findall(source))
    names.update(_WIDGET_CTOR_CALL_RE.findall(source))
    for class_name in known_class_names:
        if re.search(rf"\b{re.escape(class_name)}\s*\(", source):
            names.add(class_name)
    return names


def _is_ctor_self_referential_widget_build(content: str, class_name: str) -> bool:
    if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", content):
        return False
    build = _widget_build_snippet(content, class_name=class_name)
    return _bare_widget_ctor_return_class(build) == class_name


def _planned_has_widget_consumers(planned) -> bool:
    from .paths import _is_widget_consumer_seed_path

    return any(_is_widget_consumer_seed_path(path.replace("\\", "/")) for path in planned)


def transitively_referenced_widget_paths(planned) -> set[str]:
    """Return ``lib/widgets`` paths reachable from screens, layouts, and other widgets."""
    from .paths import _is_widget_consumer_seed_path

    class_paths = _widget_class_paths(dict(planned))
    if not class_paths:
        return set()

    known_class_names = frozenset(class_paths)
    reachable: set[str] = set()
    queue: list[str] = []
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart") or not _is_widget_consumer_seed_path(normalized):
            continue
        for class_name in _collect_widget_use_class_names(content, known_class_names):
            widget_path = _widget_path_for_ctor_name(planned, class_name)
            if widget_path is None or widget_path in reachable:
                continue
            reachable.add(widget_path)
            queue.append(widget_path)

    while queue:
        widget_path = queue.pop()
        widget_content = planned.get(widget_path, "")
        for class_name in _collect_widget_use_class_names(widget_content, known_class_names):
            nested_path = _widget_path_for_ctor_name(planned, class_name)
            if nested_path is None or nested_path in reachable:
                continue
            reachable.add(nested_path)
            queue.append(nested_path)
    return reachable


def consolidate_planned_widget_paths(planned: dict[str, str]) -> dict[str, str]:
    """Merge alias widget files onto ``lib/widgets/<to_snake_case(ClassName)>.dart``."""
    updated = dict(planned)
    for class_name, paths in _group_paths_by_class(updated).items():
        preferred = preferred_widget_path_for_class(class_name)
        if not paths:
            continue
        source_path = _pick_canonical_widget_path(paths, updated) if len(paths) > 1 else paths[0]
        body = updated.get(source_path, "")
        for path in paths:
            if path != preferred:
                updated.pop(path, None)
        if body:
            updated[preferred] = body
            if source_path != preferred:
                logger.info(
                    "Consolidated widget {} onto {}",
                    source_path,
                    preferred,
                )
    return updated


def reconcile_cluster_variant_args(planned: dict[str, str]) -> dict[str, str]:
    """Strip cluster variant args from layout when widget files do not declare them."""
    from .ast_helpers import _strip_named_param_in_widget_calls, _widget_declares_param

    widget_files = {
        path: content
        for path, content in planned.items()
        if path.startswith("lib/widgets/") and path.endswith(".dart")
    }
    if not widget_files:
        return planned

    class_params: dict[str, set[str]] = {}
    for content in widget_files.values():
        class_name = _primary_public_widget_class_name(content)
        if class_name is None:
            continue
        declared = class_params.setdefault(class_name, set())
        for param in _CLUSTER_VARIANT_PARAMS:
            if _widget_declares_param(content, param):
                declared.add(param)

    updated = dict(planned)
    for path, content in planned.items():
        if not path.startswith("lib/generated/") or not path.endswith("_layout.dart"):
            continue
        layout_source = content
        for class_name, declared_params in class_params.items():
            for param in _CLUSTER_VARIANT_PARAMS:
                if param in declared_params:
                    continue
                layout_source = _strip_named_param_in_widget_calls(
                    layout_source,
                    class_name,
                    param,
                )
        updated[path] = layout_source
    return updated


def find_missing_planned_widget_classes(planned: dict[str, str]) -> list[str]:
    """Detect consumer ``FooWidget()`` calls without a non-empty planned ``lib/widgets`` file."""
    from .paths import _is_widget_consumer_entry_path

    class_paths = _widget_class_paths(planned)
    errors: list[str] = []
    for path, class_name in _widget_class_names_by_path(planned).items():
        content = planned.get(path, "")
        if _is_foreign_delegate_widget_build(content, class_name):
            build = _widget_build_snippet(content, class_name=class_name)
            foreign = _bare_widget_ctor_return_class(build)
            if foreign in (None, "__context_widget__"):
                refs = sorted(
                    {
                        name
                        for name in re.findall(r"\bconst\s+(\w+Widget)\s*\(", build)
                        if name != class_name
                    }
                )
                foreign = refs[0] if refs else "another widget"
            rel = path.replace("\\", "/")
            errors.append(f"{rel} build only delegates to {foreign}")
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not _is_widget_consumer_entry_path(normalized):
            continue
        for class_name, widget_path in class_paths.items():
            if not re.search(rf"\b{re.escape(class_name)}\s*\(", content):
                continue
            widget_body = (planned.get(widget_path) or "").strip()
            if not widget_body or _primary_public_widget_class_name(widget_body) is None:
                errors.append(
                    f"{normalized} references {class_name} but {widget_path} is missing or empty"
                )
        for match in _WIDGET_CTOR_CALL_RE.finditer(content):
            name = match.group(1)
            if name in _FLUTTER_SDK_WIDGET_CTORS or name in class_paths:
                continue
            if _widget_path_for_ctor_name(planned, name) is not None:
                continue
            errors.append(
                f"{normalized} calls {name}() but no matching lib/widgets file is planned"
            )
    return errors


def ensure_planned_widget_manifest(planned: dict[str, str]) -> None:
    """Fail fast when screens/layouts reference widgets missing from planned files."""
    from figma_flutter_agent.errors import GenerationError

    missing = find_missing_planned_widget_classes(planned)
    if missing:
        preview = "; ".join(missing[:8])
        if len(missing) > 8:
            preview += f" (+{len(missing) - 8} more)"
        raise GenerationError(
            f"Planned Dart references widget classes without lib/widgets bodies: {preview}"
        )


def _dedupe_screen_class_definitions(planned: dict[str, str]) -> dict[str, str]:
    """Drop duplicate primary screen class declarations from planned screen files."""
    from figma_flutter_agent.generator.dart.llm_codegen import dedupe_primary_widget_class
    from figma_flutter_agent.parser.navigation import _screen_class_name

    updated = dict(planned)
    for path, content in planned.items():
        if not path.endswith("_screen.dart"):
            continue
        feature = Path(path).stem.removesuffix("_screen")
        class_name = _screen_class_name(feature)
        deduped = dedupe_primary_widget_class(content, class_name)
        if deduped != content:
            updated[path] = deduped
    return updated
