"""Reconcile planned Dart files before analyze and write."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from pathlib import Path

from loguru import logger

from figma_flutter_agent.assets.screen_frame import sanitize_dart_blocked_assets
from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.checks.text_scaler import (
    remediate_text_scaler_contract,
)
from figma_flutter_agent.generator.dart.postprocess import (
    discover_widgets_requiring_on_pressed,
    ensure_required_on_pressed_callbacks,
    process_generated_dart_source,
    sanitize_named_only_widget_calls,
)
from figma_flutter_agent.generator.dart.postprocess_params import strip_named_parameter
from figma_flutter_agent.generator.figma_anchor import ensure_screen_stack_paint_order
from figma_flutter_agent.generator.paths import ImportContext
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens
from figma_flutter_agent.tools.ast_sidecar import AST_SIDECAR_MAX_SOURCE_BYTES

_CLUSTER_VARIANT_PARAMS = ("isForward",)

_LARGE_PLANNED_DART_BYTES = AST_SIDECAR_MAX_SOURCE_BYTES
_PROACTIVE_LAYOUT_DELEGATE_SCREEN_BYTES = 8_192
_MAX_WIDGET_CONSTRUCTOR_PARAM_CHARS = 2000
_WIDGET_CLASS_RE = re.compile(
    r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)


def _primary_public_widget_class_name(content: str) -> str | None:
    """Return the exported widget class, ignoring private layout helper widgets."""
    public_names = [
        match.group("name")
        for match in _WIDGET_CLASS_RE.finditer(content)
        if not match.group("name").startswith("_")
    ]
    if not public_names:
        return None
    widget_names = [name for name in public_names if name.endswith("Widget")]
    if widget_names:
        return widget_names[-1]
    return public_names[-1]
_PACKAGE_IMPORT_RE = re.compile(r"^import\s+'package:(?P<package>[^/]+)/")
_SDK_PACKAGE_NAMES = frozenset(
    {
        "flutter",
        "flutter_svg",
        "flutter_bloc",
        "auto_route",
        "meta",
    }
)


def _widget_declares_param(widget_source: str, param_name: str) -> bool:
    patterns = (
        rf"\bthis\.{re.escape(param_name)}\b",
        rf"\bfinal\s+\w+\s+{re.escape(param_name)}\b",
        rf"\brequired\s+this\.{re.escape(param_name)}\b",
    )
    return any(re.search(pattern, widget_source) for pattern in patterns)


def _strip_named_param_in_widget_calls(
    source: str,
    class_name: str,
    param_name: str,
) -> str:
    parts: list[str] = []
    index = 0
    while True:
        start = source.find(class_name, index)
        if start == -1:
            parts.append(source[index:])
            break
        parts.append(source[index:start])
        paren_start = source.find("(", start)
        if paren_start == -1 or paren_start > start + len(class_name) + 2:
            parts.append(source[start : start + len(class_name)])
            index = start + len(class_name)
            continue
        paren_end = _find_matching_paren(source, paren_start)
        if paren_end is None:
            parts.append(source[start:])
            break
        block = source[start : paren_end + 1]
        parts.append(strip_named_parameter(block, param_name))
        index = paren_end + 1
    return "".join(parts)


def _find_matching_paren(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "(":
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(open_index, len(source)):
        char = source[index]
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
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _find_matching_brace(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "{":
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escape = False

    for index in range(open_index, len(source)):
        char = source[index]
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
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _iter_top_level_brace_inners(source: str) -> list[str]:
    """Return inner text for each ``{...}`` block using linear brace matching."""
    inners: list[str] = []
    index = 0
    length = len(source)
    while index < length:
        while index < length and source[index] != "{":
            index += 1
        if index >= length:
            break
        close = _find_matching_brace(source, index)
        if close is None:
            break
        inners.append(source[index + 1 : close])
        index = close + 1
    return inners


def reconcile_cluster_variant_args(planned: dict[str, str]) -> dict[str, str]:
    """Strip cluster variant args from layout when widget files do not declare them."""
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


def _detect_package_name(planned: dict[str, str]) -> str:
    for content in planned.values():
        for line in content.splitlines():
            match = _PACKAGE_IMPORT_RE.match(line.strip())
            if match is None:
                continue
            package = match.group("package")
            if package in _SDK_PACKAGE_NAMES:
                continue
            return package
    return "demo_app"


_WIDGET_IMPORT_RE = re.compile(r"^import\s+'(?P<uri>package:[^']+/widgets/[^']+)';")
_RELATIVE_IMPORT_RE = re.compile(r"^import\s+['\"](?P<uri>[^'\"]+)['\"]\s*;\s*$")
_LLM_WIDGET_IMPORT_COMMENT_RE = re.compile(
    r"Import prebuilt dependencies|structural invariants",
    re.IGNORECASE,
)


def strip_llm_relative_widget_imports(content: str) -> str:
    """Remove bare ``import 'foo_widget.dart'`` paths LLMs add inside ``screenCode``."""
    kept: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if _LLM_WIDGET_IMPORT_COMMENT_RE.search(stripped) and stripped.startswith("//"):
            continue
        match = _RELATIVE_IMPORT_RE.match(stripped)
        if match is not None:
            uri = match.group("uri")
            if uri.startswith("package:") or uri.startswith("dart:"):
                kept.append(line)
                continue
            if "/" in uri or uri.startswith("."):
                kept.append(line)
                continue
            if uri.endswith(".dart"):
                continue
        kept.append(line)
    return "\n".join(kept)


def strip_unused_widget_imports(content: str, planned: dict[str, str]) -> str:
    """Drop widget imports when the screen body does not reference the class."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return content
    package_name = _detect_package_name(planned)
    import_ctx = ImportContext(
        package_name=package_name,
        use_package_imports=True,
        source_file="lib/features/screen.dart",
    )
    uri_to_class = {
        import_ctx.uri(path.removeprefix("lib/")): class_name
        for class_name, path in class_paths.items()
    }
    kept: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        pkg_match = _WIDGET_IMPORT_RE.match(stripped)
        if pkg_match is not None:
            class_name = uri_to_class.get(pkg_match.group("uri"))
            if class_name is not None and not re.search(
                rf"\b{re.escape(class_name)}\b",
                content,
            ):
                continue
        kept.append(line)
    return "\n".join(kept)


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


def _normalized_widget_stem(stem: str) -> str:
    from figma_flutter_agent.generator.layout.common import to_pascal_case, to_snake_case

    return to_snake_case(to_pascal_case(stem))


_WIDGET_BUILD_HEADER_RE = re.compile(
    r"@override\s+Widget\s+build\s*\([^)]*\)\s*(?:\{|=>)"
)
_WIDGET_BUILD_HEADER_FALLBACK_RE = re.compile(
    r"Widget\s+build\s*\([^)]*\)\s*(?:\{|=>)"
)


def _widget_class_decl_index(content: str, class_name: str) -> int | None:
    match = re.search(rf"\bclass\s+{re.escape(class_name)}\s+extends\b", content)
    return match.start() if match else None


def _widget_class_build_header_match(
    content: str, class_name: str
) -> tuple[int, int, str] | None:
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
    return content[:start] + patched_build + content[end:]


def _is_self_referential_widget_build(content: str, class_name: str) -> bool:
    if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", content):
        return False
    build = _widget_build_snippet(content, class_name=class_name)
    called = _bare_widget_ctor_return_class(build)
    if called == "__context_widget__":
        return True
    return called == class_name


def _is_foreign_delegate_widget_build(content: str, class_name: str) -> bool:
    """``build`` only forwards to another widget class (wrong or stale subtree body)."""
    if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", content):
        return False
    build = _widget_build_snippet(content, class_name=class_name, max_chars=4000)
    if "SvgPicture.asset" in build or "Image.asset" in build:
        return False
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
        name
        for name in re.findall(r"\bconst\s+(\w+Widget)\s*\(", build)
        if name != class_name
    ]
    return bool(foreign)


_CLUSTER_GROUP_WIDGET_STEM_RE = re.compile(r"^group\d+", re.IGNORECASE)


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


def preferred_widget_path_for_class(class_name: str) -> str:
    from figma_flutter_agent.generator.layout.common import to_snake_case

    return f"lib/widgets/{to_snake_case(class_name)}.dart"


def _widget_lib_path_for_class(class_name: str) -> str:
    return preferred_widget_path_for_class(class_name)


def consolidate_planned_widget_paths(planned: dict[str, str]) -> dict[str, str]:
    """Merge alias widget files onto ``lib/widgets/<to_snake_case(ClassName)>.dart``."""
    updated = dict(planned)
    for class_name, paths in _group_paths_by_class(updated).items():
        preferred = preferred_widget_path_for_class(class_name)
        if not paths:
            continue
        source_path = (
            _pick_canonical_widget_path(paths, updated) if len(paths) > 1 else paths[0]
        )
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


def _is_shrink_only_widget_source(content: str) -> bool:
    if "SvgPicture.asset" in content or "Image.asset" in content:
        return False
    build = _widget_build_snippet(content)
    if "Stack(" in build or "Positioned(" in build:
        return False
    return bool(
        re.search(r"return\s+const\s+SizedBox\.shrink\(\)\s*;", build)
        or re.search(r"=>\s*const\s+SizedBox\.shrink\(\)\s*;", build)
    )


def _is_deterministic_widget_path(normalized_path: str) -> bool:
    return normalized_path.startswith("lib/widgets/")


def _is_generated_layout_path(normalized_path: str) -> bool:
    return normalized_path.startswith("lib/generated/") and normalized_path.endswith("_layout.dart")


def _skips_codegen_ast_pass(normalized_path: str, sanitized: str) -> bool:
    if normalized_path.startswith("test/capture/"):
        return True
    if _is_deterministic_widget_path(normalized_path):
        return True
    if _is_generated_layout_path(normalized_path):
        return True
    if normalized_path.startswith("lib/theme/"):
        return True
    if normalized_path.endswith("_screen.dart") and _screen_is_layout_delegate(sanitized):
        return True
    return (
        normalized_path.endswith("_screen.dart")
        and "class GeneratedScreenShell" in sanitized
        and _is_large_planned_dart(sanitized)
    )


def _screen_is_layout_delegate(screen_source: str) -> bool:
    if "Stack(" in screen_source or "Positioned(" in screen_source:
        return False
    return bool(re.search(r"const\s+\w+Layout\s*\(\s*\)", screen_source))


_SCREEN_ARTBOARD_PREVIEW_IN_BUILD_RE = re.compile(
    r"class\s+(?!GeneratedScreenShell\b)\w+Screen\b[\s\S]*?"
    r"if\s*\(\s*_artboardPreview(?:Width|Height)\b",
    re.MULTILINE,
)
_INVALID_SCREEN_CLASS_NAME_RE = re.compile(r"\bclass\s+\d\w*")
_SCREEN_LAYOUT_POLLUTION_MARKERS = (
    "designWidth",
    "designHeight",
    "canvasWidth",
    "canvasHeight",
)


def _screen_needs_layout_delegate_fallback(screen_source: str) -> bool:
    """True when LLM screen code must be replaced with a layout delegate stub."""
    if _screen_is_layout_delegate(screen_source):
        return False
    if _INVALID_SCREEN_CLASS_NAME_RE.search(screen_source):
        return True
    if any(marker in screen_source for marker in _SCREEN_LAYOUT_POLLUTION_MARKERS):
        return True
    return _SCREEN_ARTBOARD_PREVIEW_IN_BUILD_RE.search(screen_source) is not None


def force_polluted_feature_screens_to_layout(
    planned: dict[str, str],
    *,
    package_name: str = "demo_app",
    responsive_enabled: bool = True,
    max_web_width: int = 1200,
    project_dir: Path | None = None,
) -> dict[str, str]:
    """Replace analyzer-poisoned feature screens with deterministic layout delegates."""
    replace_paths: list[str] = []
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/features/") or not normalized.endswith("_screen.dart"):
            continue
        if not _screen_needs_layout_delegate_fallback(content):
            continue
        feature = Path(normalized).parent.name
        if not _layout_delegate_available(
            planned,
            feature,
            project_dir=project_dir,
        ):
            continue
        replace_paths.append(normalized)
        logger.warning(
            "Replacing polluted {} with layout delegate (undefined layout tokens or invalid class name)",
            normalized,
        )
    if not replace_paths:
        return planned
    return fallback_unparseable_screens_to_layout(
        planned,
        tuple(replace_paths),
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        max_web_width=max_web_width,
    )


_SCREEN_CLASS_OPEN_RE = re.compile(
    r"(class\s+(?!GeneratedScreenShell\b)\w+Screen\s+extends\s+\w+\s*\{)"
)


def _inject_artboard_preview_fields_if_missing(source: str) -> str:
    """Inject _artboardPreview static fields into a screen class that references them.

    The LLM sometimes copies _artboardPreviewWidth/_artboardPreviewHeight from the
    GeneratedScreenShell template context into the screen class build() method. Those
    fields are only declared in GeneratedScreenShell, so the screen class gets an
    'undefined identifier' analyzer error. This function detects the pattern and
    injects the static field declarations into the screen class body.
    """
    from figma_flutter_agent.generator.layout.common import (
        ARTBOARD_PREVIEW_CLASS_FIELDS,
        ARTBOARD_PREVIEW_LAYOUT_MARKER,
    )

    if ARTBOARD_PREVIEW_LAYOUT_MARKER not in source:
        return source
    if "static final double _artboardPreviewWidth" in source:
        # Fields already declared (either by GeneratedScreenShell or prior injection).
        # Check if the screen class also has a declaration — if only GeneratedScreenShell
        # has it we still need to inject into the screen class.
        # Simple heuristic: count occurrences; if only one class has them, inject into screen.
        if source.count("static final double _artboardPreviewWidth") >= 2:
            return source
        # Only one declaration — could be GeneratedScreenShell only; fall through to inject.
        match = _SCREEN_CLASS_OPEN_RE.search(source)
        if match is None:
            return source
        # Check if the declaration appears AFTER the screen class opening.
        decl_idx = source.index("static final double _artboardPreviewWidth")
        if decl_idx > match.start():
            return source  # already inside screen class
        # Declaration is before screen class (i.e., inside GeneratedScreenShell) → inject.
    match = _SCREEN_CLASS_OPEN_RE.search(source)
    if match is None:
        return source
    insert_pos = match.end()
    return source[:insert_pos] + "\n" + ARTBOARD_PREVIEW_CLASS_FIELDS + source[insert_pos:]


def _generated_layout_path_for_feature(feature: str) -> str:
    return f"lib/generated/{feature}_layout.dart"


def _layout_source_for_feature(
    planned: Mapping[str, str],
    feature: str,
    *,
    project_dir: Path | None = None,
) -> str | None:
    """Return deterministic layout Dart for ``feature`` from planned files or disk."""
    layout_path = _generated_layout_path_for_feature(feature)
    located = planned_content_for_path(planned, layout_path)
    if located is not None:
        return located[1]
    if project_dir is not None:
        disk_path = project_dir / layout_path
        if disk_path.is_file():
            return disk_path.read_text(encoding="utf-8")
    return None


def _layout_delegate_available(
    planned: Mapping[str, str],
    feature: str,
    *,
    project_dir: Path | None = None,
) -> bool:
    """True when a non-trivial deterministic layout file exists for ``feature``."""
    layout_source = _layout_source_for_feature(
        planned,
        feature,
        project_dir=project_dir,
    )
    if not layout_source or not layout_source.strip():
        return False
    from figma_flutter_agent.generator.layout.common import to_pascal_case

    layout_class = f"{to_pascal_case(feature)}Layout"
    if f"class {layout_class}" not in layout_source:
        return False
    return "Widget build(BuildContext context)" in layout_source


def force_oversized_feature_screens_to_layout(
    planned: dict[str, str],
    *,
    package_name: str = "demo_app",
    responsive_enabled: bool = True,
    max_web_width: int = 1200,
    max_screen_bytes: int | None = None,
) -> dict[str, str]:
    """Replace bloated feature screens with a layout delegate when layout codegen exists.

    IR/LLM materialization can inflate ``*_screen.dart`` to hundreds of KB while
    ``lib/generated/*_layout.dart`` already holds the deterministic UI. Keeping both
    duplicates slows ``dart format`` and breaks AST size limits.
    """
    byte_limit = max_screen_bytes if max_screen_bytes is not None else _LARGE_PLANNED_DART_BYTES
    replace_paths: list[str] = []
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/features/") or not normalized.endswith("_screen.dart"):
            continue
        if _screen_is_layout_delegate(content):
            continue
        if len(content.encode("utf-8")) <= byte_limit:
            continue
        feature = Path(normalized).parent.name
        if not _layout_delegate_available(planned, feature):
            continue
        replace_paths.append(normalized)
        logger.warning(
            "Replacing oversized {} ({} bytes) with layout delegate",
            normalized,
            len(content.encode("utf-8")),
        )
    if not replace_paths:
        return planned
    return fallback_unparseable_screens_to_layout(
        planned,
        tuple(replace_paths),
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        max_web_width=max_web_width,
    )


def _is_large_planned_dart(content: str) -> bool:
    return len(content.encode("utf-8")) > _LARGE_PLANNED_DART_BYTES


def split_oversized_layout_dart(
    layout_path: str,
    content: str,
    *,
    max_chunk_bytes: int | None = None,
) -> dict[str, str]:
    """Split an oversized layout file into shell + body chunks (INV-AST-COVERAGE)."""
    limit = max_chunk_bytes or _LARGE_PLANNED_DART_BYTES
    if len(content.encode("utf-8")) <= limit:
        return {layout_path: content}
    from figma_flutter_agent.tools.ast_sidecar import _discover_figma_node_ids

    base = layout_path.replace("_layout.dart", "")
    shell_path = f"{base}_shell.dart"
    node_ids = _discover_figma_node_ids(content)
    if not node_ids:
        return {layout_path: content}
    chunks: dict[str, str] = {}
    header_end = content.find("class ")
    header = content[:header_end] if header_end > 0 else ""
    shell = (
        f"{header}"
        f"// Layout shell - body widgets extracted for chunked AST passes.\n"
        f"class _LayoutShell {{ const _LayoutShell(); }}\n"
    )
    chunks[shell_path] = shell
    for index, node_id in enumerate(node_ids):
        from figma_flutter_agent.tools.ast_sidecar import extract_widget_by_figma_id

        snippet = extract_widget_by_figma_id(content, node_id)
        if snippet is None:
            continue
        chunk_path = f"{base}_body_{index}.dart"
        chunks[chunk_path] = f"// figma chunk {node_id}\n{snippet}\n"
    if len(chunks) <= 1:
        return {layout_path: content}
    return chunks


def _path_skips_ast_reconcile(normalized_path: str) -> bool:
    if normalized_path.startswith("lib/widgets/"):
        return True
    if normalized_path.startswith("lib/theme/"):
        return True
    if normalized_path == "lib/main.dart":
        return True
    return normalized_path.startswith("test/")


def _scoped_ast_reconcile_paths(planned: Mapping[str, str]) -> frozenset[str]:
    """Feature screens only — not theme, layout, widgets, main, or test harness."""
    scoped: set[str] = set()
    for path in planned:
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart"):
            continue
        if _path_skips_ast_reconcile(normalized):
            continue
        if normalized.startswith("lib/features/"):
            scoped.add(normalized)
    return frozenset(scoped)


def _skips_typography_collapse(normalized_path: str) -> bool:
    return normalized_path.startswith(
        ("lib/widgets/", "lib/generated/", "lib/theme/")
    )


def _any_widget_needs_disk_recovery(planned: Mapping[str, str]) -> bool:
    for class_name, path in _widget_class_paths(planned).items():
        if _widget_body_needs_recovery(planned.get(path, ""), class_name):
            return True
    return False


def _sanitize_ingested_widget_source(
    source: str,
    *,
    widget_path: str | None = None,
) -> str:
    """Delimiter/orphan fixes for renderer-produced bodies (codegen AST already ran)."""
    from figma_flutter_agent.generator.dart.postprocess import (
        ensure_app_layout_import,
        ensure_dart_ui_import,
        strip_self_widget_import,
    )
    from figma_flutter_agent.generator.dart.syntax_repairs import sanitize_planned_widget_syntax

    updated = sanitize_planned_widget_syntax(source)
    updated = ensure_app_layout_import(updated)
    updated = ensure_dart_ui_import(updated)
    if widget_path is not None:
        updated = strip_self_widget_import(updated, widget_path=widget_path)
    return updated


def _widget_body_needs_recovery(content: str, class_name: str) -> bool:
    if _is_self_referential_widget_build(content, class_name):
        return True
    if _is_foreign_delegate_widget_build(content, class_name):
        return True
    if len(content) > 500 and "Stack(" in content:
        return False
    return not ("SvgPicture.asset" in content or "Positioned(" in content)


def absorb_disk_widget_alias_bodies(
    planned: dict[str, str],
    project_dir: Path | None,
) -> dict[str, str]:
    """Replace stub widget sources with a richer on-disk file sharing the same class."""
    if project_dir is None or not project_dir.is_dir():
        return planned

    widgets_dir = project_dir / "lib" / "widgets"
    if not widgets_dir.is_dir():
        return planned

    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    updated = dict(planned)
    for class_name, canon_path in _widget_class_paths(updated).items():
        content = updated.get(canon_path, "")
        if not _widget_body_needs_recovery(content, class_name):
            continue
        canon_norm = _normalized_widget_stem(Path(canon_path).stem)
        best_rel: str | None = None
        best_source: str | None = None
        best_score = -1
        for dart_file in widgets_dir.glob("*.dart"):
            rel = f"lib/widgets/{dart_file.name}"
            if rel == canon_path:
                continue
            if _normalized_widget_stem(dart_file.stem) != canon_norm:
                continue
            disk_source = dart_file.read_text(encoding="utf-8")
            if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", disk_source):
                continue
            if _is_self_referential_widget_build(disk_source, class_name):
                continue
            score = len(disk_source)
            if score > best_score:
                best_score = score
                best_rel = rel
                best_source = disk_source
        if best_source is None or best_rel is None:
            continue
        disk_source = _sanitize_ingested_widget_source(best_source)
        if validate_dart_delimiters(disk_source) is not None:
            logger.warning(
                "Skipping absorb {} for {}: invalid Dart after sanitize",
                best_rel,
                class_name,
            )
            continue
        updated[canon_path] = disk_source
        logger.info(
            "Absorbed widget body for {} from disk alias {}",
            class_name,
            best_rel,
        )
    return updated


_HYDRATE_SHA_MARKER_RE = re.compile(
    r"^// figma-flutter-hydrate-sha256:([a-f0-9]{64})\n",
    re.MULTILINE,
)


def _hydrate_content_digest(source: str) -> str:
    import hashlib

    body = _HYDRATE_SHA_MARKER_RE.sub("", source, count=1)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _stamp_hydrate_digest(source: str, digest: str) -> str:
    body = _HYDRATE_SHA_MARKER_RE.sub("", source, count=1)
    return f"// figma-flutter-hydrate-sha256:{digest}\n{body}"


def hydrate_planned_widget_files_from_project(
    planned: dict[str, str],
    project_dir: Path | None,
) -> dict[str, str]:
    """Merge on-disk ``lib/widgets`` bodies referenced by screens into ``planned``."""
    if project_dir is None or not project_dir.is_dir():
        return planned

    updated = dict(planned)
    widget_use_re = re.compile(r"const\s+(\w+Widget)\s*\(")
    for path, content in planned.items():
        if not path.endswith("_screen.dart"):
            continue
        for class_name in sorted(set(widget_use_re.findall(content))):
            widget_rel = _widget_lib_path_for_class(class_name)
            existing = updated.get(widget_rel)
            if (
                existing is not None
                and not _is_shrink_only_widget_source(existing)
                and not _is_foreign_delegate_widget_build(existing, class_name)
            ):
                continue
            disk_path = project_dir / widget_rel
            if not disk_path.is_file():
                continue
            disk_source = disk_path.read_text(encoding="utf-8")
            if _is_shrink_only_widget_source(disk_source):
                continue
            if _is_foreign_delegate_widget_build(disk_source, class_name):
                continue
            from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

            disk_source = _sanitize_ingested_widget_source(disk_source)
            if validate_dart_delimiters(disk_source) is not None:
                logger.warning(
                    "Skipping hydrate {} from disk: invalid Dart after sanitize",
                    widget_rel,
                )
                continue
            disk_digest = _hydrate_content_digest(disk_source)
            if existing is not None and _hydrate_content_digest(existing) == disk_digest:
                continue
            updated[widget_rel] = _stamp_hydrate_digest(disk_source, disk_digest)
            logger.debug(
                "Hydrated {} from project disk for {}",
                widget_rel,
                class_name,
            )
    return updated


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


def _group_paths_by_class(planned: dict[str, str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path, class_name in _widget_class_names_by_path(planned).items():
        grouped.setdefault(class_name, []).append(path)
    return grouped


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


_WIDGET_USE_RE = re.compile(r"\b(\w+Widget)\s*\(")


def _collect_widget_use_class_names(source: str) -> set[str]:
    return set(_WIDGET_USE_RE.findall(source))


def _is_widget_consumer_entry_path(normalized_path: str) -> bool:
    if normalized_path.startswith("lib/features/") and normalized_path.endswith("_screen.dart"):
        return True
    if not normalized_path.startswith("lib/generated/"):
        return False
    return normalized_path.endswith("_layout.dart") or "_chunk_" in normalized_path


def _is_ctor_self_referential_widget_build(content: str, class_name: str) -> bool:
    if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", content):
        return False
    build = _widget_build_snippet(content, class_name=class_name)
    return _bare_widget_ctor_return_class(build) == class_name


def transitively_referenced_widget_paths(planned: Mapping[str, str]) -> set[str]:
    """Return ``lib/widgets`` paths reachable from screens, layouts, and other widgets."""
    class_paths = _widget_class_paths(dict(planned))
    if not class_paths:
        return set()

    reachable: set[str] = set()
    queue: list[str] = []
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart") or not _is_widget_consumer_entry_path(normalized):
            continue
        for class_name in _collect_widget_use_class_names(content):
            widget_path = class_paths.get(class_name)
            if widget_path is None or widget_path in reachable:
                continue
            reachable.add(widget_path)
            queue.append(widget_path)

    while queue:
        widget_path = queue.pop()
        widget_content = planned.get(widget_path, "")
        for class_name in _collect_widget_use_class_names(widget_content):
            nested_path = class_paths.get(class_name)
            if nested_path is None or nested_path in reachable:
                continue
            reachable.add(nested_path)
            queue.append(nested_path)
    return reachable


def _planned_has_widget_consumers(planned: Mapping[str, str]) -> bool:
    return any(_is_widget_consumer_entry_path(path.replace("\\", "/")) for path in planned)


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


def strip_orphan_widget_imports(
    content: str,
    planned: dict[str, str],
    *,
    source_file: str,
) -> str:
    """Remove widget imports that point at files no longer present in ``planned``."""
    package_name = _detect_package_name(planned)
    import_ctx = ImportContext(
        package_name=package_name,
        use_package_imports=True,
        source_file=source_file,
    )
    valid_uris = {
        import_ctx.uri(path.removeprefix("lib/"))
        for path in planned
        if path.startswith("lib/widgets/") and path.endswith(".dart")
    }
    if not valid_uris:
        return content

    lines = content.splitlines()
    kept: list[str] = []
    for line in lines:
        match = _WIDGET_IMPORT_RE.match(line.strip())
        if match is None or match.group("uri") in valid_uris:
            kept.append(line)
    return "\n".join(kept)


def strip_ambiguous_widget_imports(
    content: str,
    planned: dict[str, str],
    *,
    source_file: str,
) -> str:
    """Remove widget imports that export the same class name as another imported file."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return content

    package_name = _detect_package_name(planned)
    import_ctx = ImportContext(
        package_name=package_name,
        use_package_imports=True,
        source_file=source_file,
    )
    class_names_by_path = _widget_class_names_by_path(planned)
    canonical_uri_by_class = {
        class_name: import_ctx.uri(path.removeprefix("lib/"))
        for class_name, path in class_paths.items()
    }

    lines = content.splitlines()
    imported: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        match = _WIDGET_IMPORT_RE.match(line.strip())
        if match is None:
            continue
        uri = match.group("uri")
        for path, class_name in class_names_by_path.items():
            if import_ctx.uri(path.removeprefix("lib/")) != uri:
                continue
            imported.append((index, uri, class_name))
            break

    class_imports: dict[str, list[tuple[int, str]]] = {}
    for index, uri, class_name in imported:
        class_imports.setdefault(class_name, []).append((index, uri))

    lines_to_remove: set[int] = set()
    for class_name, imports in class_imports.items():
        if len(imports) < 2:
            continue
        canonical_uri = canonical_uri_by_class.get(class_name)
        for index, uri in imports:
            if uri != canonical_uri:
                lines_to_remove.add(index)

    if not lines_to_remove:
        return content
    return "\n".join(line for index, line in enumerate(lines) if index not in lines_to_remove)


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


def _insert_import_lines(content: str, imports: list[str]) -> str:
    if not imports:
        return content
    lines = content.splitlines()
    last_import_idx = -1
    for index, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = index
    insert_idx = last_import_idx + 1 if last_import_idx >= 0 else 0
    for import_line in imports:
        if import_line in content:
            continue
        lines.insert(insert_idx, import_line)
        insert_idx += 1
    return "\n".join(lines)


def _consumer_paths_needing_widget_imports(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("lib/features/") and normalized.endswith("_screen.dart"):
        return True
    if normalized.startswith("lib/widgets/") and normalized.endswith(".dart"):
        return True
    if not normalized.startswith("lib/generated/"):
        return False
    return normalized.endswith("_layout.dart") or "_chunk_" in normalized


def _insert_missing_widget_imports(
    content: str,
    *,
    class_paths: dict[str, str],
    package_name: str,
    source_file: str,
) -> str:
    import_ctx = ImportContext(
        package_name=package_name,
        use_package_imports=True,
        source_file=source_file,
    )
    imports_to_add: list[str] = []
    for class_name, widget_path in sorted(class_paths.items()):
        if f"{class_name}(" not in content:
            continue
        widget_uri = import_ctx.uri(widget_path.removeprefix("lib/"))
        import_line = f"import '{widget_uri}';"
        if import_line not in content:
            imports_to_add.append(import_line)
    if imports_to_add:
        content = _insert_import_lines(content, imports_to_add)
    return content


def ensure_referenced_widget_imports(planned: dict[str, str]) -> dict[str, str]:
    """Add missing widget imports when screens or layouts reference ``lib/widgets`` classes."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    package_name = _detect_package_name(planned)
    updated = dict(planned)
    for path, content in planned.items():
        if not _consumer_paths_needing_widget_imports(path):
            continue
        if _is_large_planned_dart(content):
            updated[path] = _insert_missing_widget_imports(
                content,
                class_paths=class_paths,
                package_name=package_name,
                source_file=path,
            )
            continue
        content = _insert_missing_widget_imports(
            content,
            class_paths=class_paths,
            package_name=package_name,
            source_file=path,
        )
        content = strip_llm_relative_widget_imports(content)
        content = strip_unused_widget_imports(content, updated)
        content = strip_orphan_widget_imports(content, updated, source_file=path)
        updated[path] = strip_ambiguous_widget_imports(
            content,
            updated,
            source_file=path,
        )
    return updated


def sync_widget_consumer_imports(
    planned: dict[str, str],
    *,
    skip_consolidate: bool = False,
) -> dict[str, str]:
    """Consolidate widget paths and align layout/screen import URIs with planned widgets."""
    updated = planned if skip_consolidate else consolidate_planned_widget_paths(planned)
    updated = redirect_widget_imports_to_canonical(updated)
    updated = ensure_referenced_widget_imports(updated)
    return updated


def prepare_files_for_write_commit(
    files_to_write: dict[str, str],
    planned_files: dict[str, str] | None,
    *,
    package_name: str = "demo_app",
    project_dir: Path | None = None,
    responsive_enabled: bool = True,
) -> dict[str, str]:
    """Refresh write payloads and pull in layout/screen when widget imports were reconciled."""
    if not planned_files:
        merged = dict(files_to_write)
    else:
        merged = dict(planned_files)
        merged.update(files_to_write)
    merged = force_polluted_feature_screens_to_layout(
        merged,
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        project_dir=project_dir,
    )
    if not planned_files:
        return {path: merged[path] for path in files_to_write if path in merged}

    synced = sync_widget_consumer_imports(merged, skip_consolidate=True)
    prepared = dict(files_to_write)
    for path in list(prepared):
        if path in synced:
            prepared[path] = synced[path]

    for path, content in synced.items():
        normalized = path.replace("\\", "/")
        if normalized.endswith("_layout.dart") or (
            normalized.startswith("lib/features/") and normalized.endswith("_screen.dart")
        ):
            prepared[path] = content

    class_paths = _widget_class_paths(synced)
    for path, content in synced.items():
        if not path.replace("\\", "/").startswith("lib/widgets/"):
            continue
        prepared[path] = content

    ensure_planned_widget_manifest(synced)

    for path, content in list(synced.items()):
        normalized = path.replace("\\", "/")
        if not (
            normalized.endswith("_layout.dart")
            or (
                normalized.startswith("lib/features/")
                and normalized.endswith("_screen.dart")
            )
        ):
            continue
        body = content
        for class_name, widget_path in class_paths.items():
            if re.search(rf"\b{re.escape(class_name)}\b", body):
                prepared[widget_path] = synced[widget_path]
    return prepared


def redirect_widget_imports_to_canonical(planned: dict[str, str]) -> dict[str, str]:
    """Rewrite widget import URIs so consumers target the canonical ``lib/widgets`` file."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    package_name = _detect_package_name(planned)
    from figma_flutter_agent.generator.layout.common import to_pascal_case

    updated = dict(planned)
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart"):
            continue
        if not (
            _consumer_paths_needing_widget_imports(path)
            or normalized.startswith("lib/widgets/")
        ):
            continue
        if normalized.startswith("lib/widgets/") and _is_large_planned_dart(content):
            continue
        import_ctx = ImportContext(
            package_name=package_name,
            use_package_imports=True,
            source_file=path,
        )
        lines = content.splitlines()
        changed = False
        for index, line in enumerate(lines):
            match = _WIDGET_IMPORT_RE.match(line.strip())
            if match is None:
                continue
            uri = match.group("uri")
            if "/widgets/" not in uri:
                continue
            stem = Path(uri).stem
            inferred_class = to_pascal_case(stem)
            if inferred_class not in class_paths:
                continue
            widget_path = class_paths.get(inferred_class)
            if widget_path is None:
                continue
            canonical_uri = import_ctx.uri(widget_path.removeprefix("lib/"))
            if uri == canonical_uri:
                continue
            if not re.search(rf"\b{re.escape(inferred_class)}\b", content):
                continue
            lines[index] = line.replace(uri, canonical_uri)
            changed = True
        if changed:
            updated[path] = "\n".join(lines)
    return updated


def prune_disk_widget_stem_aliases(
    project_dir: Path,
    planned: dict[str, str],
) -> list[str]:
    """Delete on-disk widget files that alias the canonical planned path for a class."""
    widgets_dir = project_dir / "lib" / "widgets"
    if not widgets_dir.is_dir():
        return []

    canonical_paths = {
        p.replace("\\", "/") for p in _widget_class_paths(planned).values()
    }
    if not canonical_paths:
        return []

    canonical_norms = {
        _normalized_widget_stem(Path(path).stem) for path in canonical_paths
    }
    removed: list[str] = []
    for dart_file in sorted(widgets_dir.glob("*.dart")):
        rel = f"lib/widgets/{dart_file.name}"
        if rel in canonical_paths:
            continue
        norm = _normalized_widget_stem(dart_file.stem)
        if norm not in canonical_norms:
            continue
        try:
            dart_file.unlink()
            removed.append(rel)
            logger.info("Removed stale widget alias on disk: {}", rel)
        except OSError as exc:
            logger.warning("Could not remove stale widget alias {}: {}", rel, exc)
    return removed


def align_widget_class_with_file_stem(planned: dict[str, str]) -> dict[str, str]:
    """Rename a widget class when the declared name disagrees with ``lib/widgets/<stem>.dart``."""
    from figma_flutter_agent.generator.layout.common import to_pascal_case
    from figma_flutter_agent.generator.subtree_widgets import _rename_widget_class

    updated = dict(planned)
    for path, content in planned.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        expected = to_pascal_case(Path(path).stem)
        actual = _primary_public_widget_class_name(content)
        if actual is None:
            continue
        if actual == expected:
            continue
        if _is_large_planned_dart(content):
            logger.warning(
                "Skipping widget class rename in large file {} ({} vs {})",
                path,
                actual,
                expected,
            )
            continue
        updated[path] = _rename_widget_class(content, actual, expected)
        logger.info(
            "Aligned widget class {} -> {} in {}",
            actual,
            expected,
            path,
        )
    return updated


def ensure_widget_sibling_imports(planned: dict[str, str]) -> dict[str, str]:
    """Add imports when Dart references another planned ``lib/widgets`` class."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    package_name = _detect_package_name(planned)
    updated = dict(planned)
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart"):
            continue
        if not (
            normalized.startswith("lib/widgets/")
            or normalized.startswith("lib/generated/")
            or (
                normalized.startswith("lib/features/")
                and normalized.endswith("_screen.dart")
            )
        ):
            continue
        import_ctx = ImportContext(
            package_name=package_name,
            use_package_imports=True,
            source_file=path,
        )
        own_class: str | None = None
        if normalized.startswith("lib/widgets/"):
            own_class = _primary_public_widget_class_name(content)
        imports_to_add: list[str] = []
        for class_name, widget_path in sorted(class_paths.items()):
            if class_name == own_class:
                continue
            if not re.search(rf"\b{re.escape(class_name)}\s*\(", content):
                continue
            widget_uri = import_ctx.uri(widget_path.removeprefix("lib/"))
            import_line = f"import '{widget_uri}';"
            if import_line not in content:
                imports_to_add.append(import_line)
        if imports_to_add:
            updated[path] = _insert_import_lines(content, imports_to_add)
    return updated


_MAX_WIDGET_ALIAS_SUFFIX_LEN = 2


def _sync_widget_build_class_references(content: str, class_name: str) -> str:
    """Rewrite numbered alias ctor names in ``build`` to the declared widget class."""
    build_match = re.search(r"@override\s+Widget\s+build\s*\([^)]*\)", content)
    if build_match is None:
        build_match = re.search(r"Widget\s+build\s*\([^)]*\)", content)
    if build_match is None:
        return content
    start = build_match.end()
    body = content[start:]
    suffix_match = re.search(r"(\d+)$", class_name)
    if suffix_match:
        suffix = suffix_match.group(1)
        if len(suffix) > _MAX_WIDGET_ALIAS_SUFFIX_LEN:
            return content
        base = class_name[: suffix_match.start()]
        pattern = rf"\b{re.escape(base)}(?!{re.escape(suffix)})\s*\("
    else:
        pattern = rf"\b{re.escape(class_name)}\d+\s*\("
    patched = re.sub(pattern, f"{class_name}(", body)
    if patched == body:
        return content
    return content[:start] + patched


def sync_widget_class_constructors(content: str) -> str:
    """Align the primary widget constructor name with the declared widget class."""
    from figma_flutter_agent.generator.dart.postprocess import repair_obsolete_dart_default_colons

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


def _constructor_decl_limit(header: str, search_from: int) -> int:
    build_match = re.search(r"@override\s+Widget\s+build", header[search_from:])
    if build_match is None:
        return len(header)
    return search_from + build_match.start()


def filter_widget_import_stems(
    stems: list[str],
    planned_files: dict[str, str],
) -> list[str]:
    """Keep only widget import stems that have a matching planned ``lib/widgets`` file."""
    return [
        stem
        for stem in stems
        if f"lib/widgets/{stem}.dart" in planned_files
    ]


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


def find_missing_planned_widget_classes(planned: dict[str, str]) -> list[str]:
    """Detect consumer ``FooWidget()`` calls without a non-empty planned ``lib/widgets`` file."""
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
        if not _consumer_paths_needing_widget_imports(normalized):
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
            errors.append(
                f"{normalized} calls {name}() but no matching lib/widgets file is planned"
            )
    return errors


def widget_import_stems_for_screen(
    screen_code: str,
    planned_files: dict[str, str],
) -> list[str]:
    """Return widget file stems referenced by class name in a screen body."""
    stems: set[str] = set()
    for class_name, widget_path in _widget_class_paths(planned_files).items():
        if re.search(rf"\b{re.escape(class_name)}\s*\(", screen_code):
            stems.add(Path(widget_path).stem)
    return sorted(stems)


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


def canonicalize_planned_path_keys(planned: dict[str, str]) -> None:
    """Use forward-slash keys so format-gate repairs hit the same entries on Windows."""
    for path in list(planned):
        normalized = path.replace("\\", "/")
        if normalized == path:
            continue
        if normalized in planned:
            planned[normalized] = planned.pop(path)
        else:
            planned[normalized] = planned.pop(path)


def planned_content_for_path(
    planned: Mapping[str, str],
    path: str,
) -> tuple[str, str] | None:
    """Return ``(normalized_path, content)`` for a project-relative Dart path."""
    normalized = path.replace("\\", "/")
    for key in (normalized, path):
        if key in planned:
            return normalized, planned[key]
    for key, content in planned.items():
        if key.replace("\\", "/") == normalized:
            return normalized, content
    return None


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


_GENERATED_SCREEN_SHELL_RE = re.compile(
    r"(/// Responsive shell injected[\s\S]*?^class GeneratedScreenShell\b[\s\S]*?^\})",
    re.MULTILINE,
)


def _extract_generated_screen_shell(prior: str) -> str:
    match = _GENERATED_SCREEN_SHELL_RE.search(prior)
    return match.group(1).strip() if match is not None else ""


def _screen_shell_block_for_fallback(*, max_web_width: int) -> str:
    """Return the canonical ``GeneratedScreenShell`` for emit-gate recovery.

    Parse-gate fallback must not reuse shell text from the failing source: chunked AST
    and delimiter repair often corrupt ``GeneratedScreenShell`` while the screen body is
    replaced separately.
    """
    return f"{_default_generated_screen_shell(max_web_width=max_web_width)}\n\n"


def _default_generated_screen_shell(*, max_web_width: int) -> str:
    return f"""/// Responsive shell injected by the generator for web/tablet max width.
class GeneratedScreenShell extends StatelessWidget {{
  const GeneratedScreenShell({{
    super.key,
    required this.child,
    this.maxWebWidth = {max_web_width},
  }});

  final Widget child;
  final double maxWebWidth;

  static final double _artboardPreviewWidth = double.tryParse(
        const String.fromEnvironment('FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH'),
      ) ??
      0;
  static final double _artboardPreviewHeight = double.tryParse(
        const String.fromEnvironment('FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT'),
      ) ??
      0;

  @override
  Widget build(BuildContext context) {{
    if (_artboardPreviewWidth > 0 && _artboardPreviewHeight > 0) {{
      return Align(
        alignment: Alignment.topLeft,
        child: ClipRect(
          child: SizedBox(
            width: _artboardPreviewWidth,
            height: _artboardPreviewHeight,
            child: ColoredBox(
              color: Theme.of(context).scaffoldBackgroundColor,
              child: child,
            ),
          ),
        ),
      );
    }}
    final layout = Theme.of(context).extension<AppLayoutExtension>();
    final resolvedMaxWidth = layout?.maxWebWidth ?? maxWebWidth;
    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      body: LayoutBuilder(
        builder: (context, constraints) {{
          final media = MediaQuery.sizeOf(context);
          final width = constraints.maxWidth.isFinite && constraints.maxWidth > 0
              ? constraints.maxWidth
              : media.width;
          final horizontalPadding = AppBreakpoints.horizontalPadding(width);
          final contentMaxWidth = AppBreakpoints.contentMaxWidth(width, resolvedMaxWidth);
          return Align(
            alignment: Alignment.topCenter,
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: contentMaxWidth),
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
                child: child,
              ),
            ),
          );
        }},
      ),
    );
  }}
}}"""


def fallback_unparseable_screens_to_layout(
    planned: dict[str, str],
    format_paths: tuple[str, ...],
    *,
    package_name: str,
    responsive_enabled: bool = True,
    max_web_width: int = 1200,
) -> dict[str, str]:
    """Last-resort: delegate screen ``build`` to the deterministic layout widget."""
    if not format_paths:
        return planned
    from figma_flutter_agent.generator.dart.llm_codegen import _layout_delegation_screen_stub
    from figma_flutter_agent.parser.navigation import _screen_class_name

    layout_theme_import = f"package:{package_name}/theme/app_layout.dart"

    for path in format_paths:
        normalized = path.replace("\\", "/")
        if not normalized.endswith("_screen.dart"):
            continue
        feature = Path(normalized).parent.name
        screen_class = _screen_class_name(feature)
        layout_class = screen_class.replace("Screen", "Layout")
        layout_import = f"package:{package_name}/generated/{feature}_layout.dart"
        located = planned_content_for_path(planned, normalized)
        prior = located[1] if located is not None else ""
        custom_block = ""
        match = re.search(
            r"// <custom-code>\n(.*?)// </custom-code>",
            prior,
            flags=re.DOTALL,
        )
        if match is not None:
            custom_block = match.group(1)
        imports = [
            "import 'package:flutter/material.dart';",
            f"import '{layout_import}';",
        ]
        shell_block = ""
        if responsive_enabled:
            # Always inject app_layout: ``prior`` may mention the URI inside a huge LLM
            # blob without a valid import line, which previously dropped AppBreakpoints.
            imports.insert(1, f"import '{layout_theme_import}';")
            shell_block = _screen_shell_block_for_fallback(max_web_width=max_web_width)
        screen_body = _layout_delegation_screen_stub(
            screen_class,
            layout_class,
            responsive_enabled=responsive_enabled,
        )
        stub = (
            "// <auto-generated>\n"
            "// Generated by figma-flutter-agent. Do not edit by hand.\n"
            "// </auto-generated>\n\n"
            + "\n".join(imports)
            + "\n\n"
            "// <custom-code>\n"
            f"{custom_block}"
            "// </custom-code>\n\n"
            f"{shell_block}"
            f"{screen_body}"
        )
        logger.warning(
            "Emit parse gate: replaced unparseable {} with layout delegate {}",
            normalized,
            layout_class,
        )
        planned[normalized] = stub
    return planned


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
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        append_missing_closers_on_lines,
        apply_format_parse_error_insertions,
        apply_planned_delimiter_balance,
        is_garbage_closer_only_line,
        is_orphan_semicolon_line,
        parse_format_error_line_numbers,
        sanitize_planned_widget_syntax,
    )
    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        trim_surplus_dart_delimiters,
        validate_dart_delimiters,
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


def _balance_planned_widget_delimiters(planned: dict[str, str]) -> dict[str, str]:
    """Repair delimiter drift on feature screens and extracted widget files."""
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        apply_planned_delimiter_balance,
        sanitize_planned_widget_syntax,
    )
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

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


def _dart_accepts_on_pressed_call_sites(path: str) -> bool:
    """True for screens and feature files — not widget class definitions."""
    normalized = path.replace("\\", "/")
    if normalized.startswith("lib/widgets/"):
        return False
    if normalized.endswith("_screen.dart"):
        return True
    return normalized.startswith("lib/features/") and normalized.endswith(".dart")


def _use_ast_sidecar_enabled(override: bool | None) -> bool:
    if override is not None:
        return override
    try:
        return Settings().agent.runtime.use_ast_sidecar
    except Exception:
        return True


def refresh_shrunk_and_delegate_planned_widgets(
    planned: dict[str, str],
    *,
    clean_tree: CleanDesignTreeNode,
    widget_suffix: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    cluster_summary: dict[str, int] | None = None,
    cluster_min_count: int = 2,
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
) -> dict[str, str]:
    """Re-render subtree/cluster widgets after shrink-only or foreign-delegate repair."""
    from figma_flutter_agent.generator.subtree_widgets import (
        _collect_subtree_specs_to_render,
        _layout_widget_class_names,
        build_cluster_render_context,
        collect_subtree_widget_specs,
        refresh_subtree_widget_planned_files,
    )
    from figma_flutter_agent.generator.widget_extractor import (
        refresh_cluster_widget_planned_files,
    )

    updated = dict(planned)
    if cluster_summary:
        updated = refresh_cluster_widget_planned_files(
            updated,
            clean_tree=clean_tree,
            cluster_summary=cluster_summary,
            min_count=cluster_min_count,
            widget_suffix=widget_suffix,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            destination_trees=destination_trees,
        )
        updated = consolidate_planned_widget_paths(updated)
    specs = list(collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix))
    if not specs:
        return updated
    layout_names = sorted(_layout_widget_class_names(updated))
    cluster_classes: dict[str, str] | None = None
    cluster_vector_variants: dict | None = None
    if cluster_summary:
        cluster_classes, cluster_vector_variants = build_cluster_render_context(
            clean_tree,
            cluster_summary=cluster_summary,
            widget_suffix=widget_suffix,
            min_count=cluster_min_count,
            destination_trees=destination_trees,
        )
    if not _collect_subtree_specs_to_render(
        updated,
        specs,
        layout_class_names=layout_names,
        clean_tree=clean_tree,
    ):
        return updated
    return refresh_subtree_widget_planned_files(
        updated,
        clean_tree=clean_tree,
        widget_suffix=widget_suffix,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )


def _apply_oversized_layout_splits(planned: dict[str, str]) -> dict[str, str]:
    """Split oversized layout files into shell/body chunks before AST reconcile."""
    updated = dict(planned)
    for path, content in list(planned.items()):
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/generated/") or not normalized.endswith("_layout.dart"):
            continue
        if not _is_large_planned_dart(content):
            continue
        chunks = split_oversized_layout_dart(normalized, content)
        if len(chunks) <= 1:
            continue
        for chunk_path, chunk_content in chunks.items():
            updated[chunk_path] = chunk_content
        updated.pop(path, None)
    return updated


def _tree_has_layout_slots(root: CleanDesignTreeNode) -> bool:
    stack = [root]
    while stack:
        node = stack.pop()
        if node.layout_slot is not None:
            return True
        stack.extend(node.children)
    return False


def reconcile_planned_dart_files(
    planned: dict[str, str],
    *,
    blocked_asset_paths: frozenset[str] | None = None,
    use_ast_sidecar: bool | None = None,
    typography_tokens: DesignTokens | None = None,
    package_name: str = "demo_app",
    clean_tree: CleanDesignTreeNode | None = None,
    ast_full_reconcile_paths: frozenset[str] | None = None,
    incremental: bool | None = None,
    project_dir: Path | None = None,
    widget_suffix: str | None = None,
    uses_svg: bool | None = None,
    use_package_imports: bool = True,
    cluster_summary: dict[str, int] | None = None,
    cluster_min_count: int = 2,
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
    reconcile_metadata: dict[str, object] | None = None,
) -> dict[str, str]:
    """Apply deterministic reconciliation and postprocess to planned Dart files."""
    from figma_flutter_agent.generator.app_typography_collapse import (
        collapse_inline_text_styles_to_app_typography,
    )

    ast_enabled = _use_ast_sidecar_enabled(use_ast_sidecar)
    ast_backends: set[str] = set()
    sidecar_skipped: set[str] = set()
    updated = force_polluted_feature_screens_to_layout(
        dict(planned),
        package_name=package_name,
        project_dir=project_dir,
    )
    updated = _apply_oversized_layout_splits(updated)
    if incremental is None:
        incremental = True
    effective_ast_paths = (
        ast_full_reconcile_paths
        if ast_full_reconcile_paths is not None
        else _scoped_ast_reconcile_paths(updated)
    )
    logger.info(
        "reconcile_planned_dart_files starting ({} dart files, incremental={}, ast_scope={})",
        sum(1 for key in planned if key.endswith(".dart")),
        incremental,
        len(effective_ast_paths),
    )
    phase_t = time.monotonic()

    def _log_reconcile_phase(label: str, *, end: bool = False) -> None:
        nonlocal phase_t
        if not end:
            logger.info("Planned reconcile phase: {}", label)
            return
        elapsed = time.monotonic() - phase_t
        if elapsed >= 0.05:
            logger.info("Planned reconcile {} {:.2f}s", label, elapsed)
        phase_t = time.monotonic()

    if incremental:
        logger.info(
            "Planned Dart incremental reconcile (AST scope: {} path(s))",
            len(effective_ast_paths),
        )
    _log_reconcile_phase("cluster_variants")
    updated = reconcile_cluster_variant_args(updated)
    _log_reconcile_phase("cluster_variants", end=True)
    _log_reconcile_phase("consolidate_widgets")
    updated = consolidate_planned_widget_paths(updated)
    updated = prune_duplicate_widget_classes(updated)
    updated = repair_self_referential_widget_builds(updated)
    updated = repair_foreign_delegate_widget_builds(updated)
    updated = repair_stale_widget_ctor_names_in_planned(updated)
    _log_reconcile_phase("consolidate_widgets", end=True)
    if not incremental and _any_widget_needs_disk_recovery(updated):
        _log_reconcile_phase("hydrate_absorb")
        updated = hydrate_planned_widget_files_from_project(updated, project_dir)
        updated = absorb_disk_widget_alias_bodies(updated, project_dir)
        _log_reconcile_phase("hydrate_absorb", end=True)
        updated = prune_duplicate_widget_classes(updated)
        updated = repair_self_referential_widget_builds(updated)
        updated = repair_foreign_delegate_widget_builds(updated)
        updated = repair_stale_widget_ctor_names_in_planned(updated)
    elif not incremental:
        logger.info("Planned reconcile: skipping hydrate/absorb (widgets already complete)")
    if clean_tree is not None and cluster_summary and uses_svg is not None and widget_suffix:
        from figma_flutter_agent.generator.widget_extractor import (
            refresh_cluster_widget_planned_files,
        )

        _log_reconcile_phase("refresh_cluster")
        updated = refresh_cluster_widget_planned_files(
            updated,
            clean_tree=clean_tree,
            cluster_summary=cluster_summary,
            min_count=cluster_min_count,
            widget_suffix=widget_suffix,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            destination_trees=destination_trees,
        )
        updated = consolidate_planned_widget_paths(updated)
        _log_reconcile_phase("refresh_cluster", end=True)
    if clean_tree is not None and widget_suffix:
        from figma_flutter_agent.generator.subtree_widgets import (
            _collect_subtree_specs_to_render,
            _layout_widget_class_names,
            build_cluster_render_context,
            collect_subtree_widget_specs,
            refresh_subtree_widget_planned_files,
        )

        specs = list(
            collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
        )
        layout_names = sorted(_layout_widget_class_names(updated))
        cluster_classes: dict[str, str] | None = None
        cluster_vector_variants: dict | None = None
        if cluster_summary and uses_svg is not None:
            cluster_classes, cluster_vector_variants = build_cluster_render_context(
                clean_tree,
                cluster_summary=cluster_summary,
                widget_suffix=widget_suffix,
                min_count=cluster_min_count,
                destination_trees=destination_trees,
            )
        if _collect_subtree_specs_to_render(
            updated,
            specs,
            layout_class_names=layout_names,
            clean_tree=clean_tree,
        ):
            _log_reconcile_phase("refresh_subtree")
            updated = refresh_subtree_widget_planned_files(
                updated,
                clean_tree=clean_tree,
                widget_suffix=widget_suffix,
                uses_svg=bool(uses_svg),
                package_name=package_name,
                use_package_imports=use_package_imports,
                cluster_classes=cluster_classes,
                cluster_vector_variants=cluster_vector_variants,
            )
            updated = consolidate_planned_widget_paths(updated)
            _log_reconcile_phase("refresh_subtree", end=True)
        else:
            logger.info("Planned reconcile: skipping refresh_subtree (widgets already valid)")
    _log_reconcile_phase("screen_dedupe")
    _log_reconcile_phase("strip_inline_widgets")
    updated = strip_inline_widget_duplicates_from_screens(updated)
    _log_reconcile_phase("strip_inline_widgets", end=True)
    _log_reconcile_phase("dedupe_screen_class")
    updated = _dedupe_screen_class_definitions(updated)
    _log_reconcile_phase("dedupe_screen_class", end=True)
    _log_reconcile_phase("balance_delimiters")
    updated = _balance_planned_widget_delimiters(updated)
    _log_reconcile_phase("balance_delimiters", end=True)
    _log_reconcile_phase("align_widget_stems")
    updated = align_widget_class_with_file_stem(updated)
    for path in list(updated.keys()):
        if path.startswith("lib/widgets/") and path.endswith(".dart"):
            synced = sync_widget_class_constructors(updated[path])
            if synced != updated[path]:
                updated[path] = synced
    _log_reconcile_phase("align_widget_stems", end=True)
    _log_reconcile_phase("prune_stale_widgets")
    updated = drop_unparseable_planned_widget_files(updated)
    updated = prune_unreferenced_planned_widgets(updated)
    _log_reconcile_phase("prune_stale_widgets", end=True)
    _log_reconcile_phase("sync_widget_imports")
    updated = sync_widget_consumer_imports(updated, skip_consolidate=True)
    _log_reconcile_phase("sync_widget_imports", end=True)
    _log_reconcile_phase("screen_dedupe", end=True)
    callback_widgets = discover_widgets_requiring_on_pressed(updated)
    blocked = blocked_asset_paths or frozenset()
    if ast_enabled:
        dart_file_count = sum(1 for key in updated if key.endswith(".dart"))
        logger.info(
            "Planned Dart reconcile starting ({} files; AST sidecar can take several minutes)",
            dart_file_count,
        )
    ast_started = time.monotonic()
    for path, content in updated.items():
        if not path.endswith(".dart"):
            continue
        if path.startswith("lib/widgets/"):
            content = sync_widget_class_constructors(content)
            from figma_flutter_agent.generator.dart.syntax_repairs import (
                strip_duplicate_key_after_super,
            )

            content = strip_duplicate_key_after_super(content)
        if path.startswith(("lib/", "test/")):
            sanitized = sanitize_dart_blocked_assets(content, blocked)
            include_text_scaler = not (
                path.startswith("lib/generated/") and path.endswith("_layout.dart")
            )
            normalized_path = path.replace("\\", "/")
            if normalized_path.startswith("test/capture/"):
                updated[path] = sanitized
                continue
            from figma_flutter_agent.generator.dart.postprocess import (
                repair_orphan_design_canvas_identifiers,
            )
            from figma_flutter_agent.generator.dart.syntax_repairs import (
                repair_broken_artboard_preview_declarations,
            )

            sanitized = repair_orphan_design_canvas_identifiers(sanitized)
            sanitized = repair_broken_artboard_preview_declarations(sanitized)
            if normalized_path.endswith("_screen.dart"):
                sanitized = _inject_artboard_preview_fields_if_missing(sanitized)
            run_full_ast = ast_enabled and normalized_path in effective_ast_paths
            if run_full_ast:
                file_started = time.monotonic()
                skip_ast = _skips_codegen_ast_pass(normalized_path, sanitized)
                if skip_ast:
                    if (
                        _is_generated_layout_path(normalized_path)
                        and _is_large_planned_dart(sanitized)
                        and clean_tree is not None
                        and _tree_has_layout_slots(clean_tree)
                    ):
                        sidecar_skipped.add(normalized_path)
                    processed = _sanitize_ingested_widget_source(
                        sanitized,
                        widget_path=normalized_path
                        if normalized_path.startswith("lib/widgets/")
                        else None,
                    )
                else:
                    logger.info("AST sidecar: {}", normalized_path)
                    processed = process_generated_dart_source(
                        sanitized,
                        include_text_scaler=include_text_scaler,
                        use_ast_sidecar=True,
                    )
                    ast_backends.add("subprocess")
                file_elapsed = time.monotonic() - file_started
                if file_elapsed >= 1.0 and not skip_ast:
                    logger.info("AST reconcile {:.1f}s: {}", file_elapsed, normalized_path)
            else:
                from figma_flutter_agent.generator.dart.postprocess import (
                    ensure_dart_ui_import,
                )

                if normalized_path.startswith("lib/widgets/"):
                    # LLM-widget: use cheap in-process pass (sidecar only when broken).
                    processed = _sanitize_ingested_widget_source(
                        sanitized,
                        widget_path=normalized_path,
                    )
                elif not normalized_path.startswith("lib/features/"):
                    # Compiler/template Dart (theme, generated, main, routes, test):
                    # structurally valid by construction — skip sidecar subprocess.
                    processed = ensure_dart_ui_import(sanitized)
                else:
                    from figma_flutter_agent.generator.dart.syntax_repairs import (
                        apply_llm_dart_syntax_repairs,
                    )

                    processed = ensure_dart_ui_import(
                        apply_llm_dart_syntax_repairs(sanitized)
                    )
            if callback_widgets and _dart_accepts_on_pressed_call_sites(path):
                processed = ensure_required_on_pressed_callbacks(
                    processed,
                    widget_names=callback_widgets,
                )
                processed = sanitize_named_only_widget_calls(
                    processed,
                    widget_names=callback_widgets,
                )
            if (
                path.endswith("_screen.dart")
                and run_full_ast
                and not _skips_codegen_ast_pass(normalized_path, processed)
            ):
                from figma_flutter_agent.generator.dart.llm_codegen import (
                    apply_clean_tree_text_to_screen,
                    apply_safe_screen_code_patch,
                )

                processed = apply_safe_screen_code_patch(
                    processed,
                    ensure_screen_stack_paint_order,
                    label="screen stack paint order",
                )
                if clean_tree is not None:
                    from figma_flutter_agent.generator.layout.flex_reconcile import (
                        apply_flex_guards_from_tree,
                    )

                    processed = apply_safe_screen_code_patch(
                        processed,
                        lambda source: apply_flex_guards_from_tree(
                            apply_clean_tree_text_to_screen(source, clean_tree),
                            clean_tree,
                        ),
                        label="screen tree text and flex",
                    )
            if (
                typography_tokens is not None
                and path.endswith(".dart")
                and run_full_ast
                and not _skips_typography_collapse(normalized_path)
                and not _skips_codegen_ast_pass(normalized_path, processed)
            ):
                processed = collapse_inline_text_styles_to_app_typography(
                    processed,
                    typography_tokens,
                    package_name=package_name,
                )
            updated[path] = processed
    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        trim_surplus_dart_delimiters,
        validate_dart_delimiters,
    )

    for path, content in list(updated.items()):
        if not path.endswith(".dart"):
            continue
        normalized_path = path.replace("\\", "/")
        repaired = content
        if normalized_path.endswith("_screen.dart"):
            trimmed = trim_surplus_dart_delimiters(repaired)
            if trimmed is not None:
                repaired = trimmed
            repaired = sanitize_screen_emit_syntax(repaired)
            repaired = repair_dart_delimiters(repaired)
        elif validate_dart_delimiters(repaired) is not None:
            sanitized = _sanitize_planned_dart_syntax(path, repaired)
            if sanitized != repaired:
                repaired = sanitized
        if repaired != content:
            updated[path] = repaired
    if ast_enabled:
        if ast_backends:
            logger.info("AST sidecar reconcile backend(s): {}", ", ".join(sorted(ast_backends)))
        logger.info("Planned Dart reconcile finished in {:.1f}s", time.monotonic() - ast_started)
    missing_widgets = find_missing_planned_widget_classes(updated)
    for message in missing_widgets:
        logger.error("Planned widget manifest: {}", message)
    from figma_flutter_agent.generator.capture_screen_test import (
        refresh_capture_tests_in_planned,
    )

    updated = refresh_capture_tests_in_planned(updated, package_name=package_name)
    updated = force_polluted_feature_screens_to_layout(
        updated,
        package_name=package_name,
        responsive_enabled=True,
        project_dir=project_dir,
    )
    updated = force_oversized_feature_screens_to_layout(
        updated,
        package_name=package_name,
        responsive_enabled=True,
        max_screen_bytes=_PROACTIVE_LAYOUT_DELEGATE_SCREEN_BYTES,
    )
    updated = force_oversized_feature_screens_to_layout(
        updated,
        package_name=package_name,
        responsive_enabled=True,
    )
    if reconcile_metadata is not None:
        reconcile_metadata["sidecar_skipped_paths"] = frozenset(sidecar_skipped)
    updated = repair_stale_widget_ctor_names_in_planned(updated)
    updated = repair_self_referential_widget_builds(updated)
    return remediate_text_scaler_contract(updated)
