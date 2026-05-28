"""Reconcile planned Dart files before analyze and write."""

from __future__ import annotations

import re
from pathlib import Path

from figma_flutter_agent.assets.screen_frame import sanitize_dart_blocked_assets
from figma_flutter_agent.config import Settings
from figma_flutter_agent.schemas import DesignTokens
from figma_flutter_agent.generator.codegen_checks import remediate_text_scaler_contract
from figma_flutter_agent.generator.figma_anchor import ensure_screen_stack_paint_order
from figma_flutter_agent.generator.dart_postprocess import (
    discover_widgets_requiring_on_pressed,
    ensure_required_on_pressed_callbacks,
    sanitize_named_only_widget_calls,
    process_generated_dart_source,
)
from figma_flutter_agent.generator.dart_postprocess_params import strip_named_parameter
from figma_flutter_agent.generator.paths import ImportContext
from loguru import logger


_CLUSTER_VARIANT_PARAMS = ("isForward",)
_WIDGET_CLASS_RE = re.compile(
    r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)
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
        match = _WIDGET_CLASS_RE.search(content)
        if match is None:
            continue
        class_name = match.group("name")
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
        match = _WIDGET_CLASS_RE.search(content)
        if match is None:
            continue
        class_names[path] = match.group("name")
    return class_names


def _pick_canonical_widget_path(paths: list[str], planned: dict[str, str]) -> str:
    def sort_key(path: str) -> tuple[int, int, str]:
        content = planned.get(path, "")
        stem = Path(path).stem
        suffix_match = re.search(r"_(\d+)$", stem)
        suffix_rank = int(suffix_match.group(1)) if suffix_match else 0
        return (-len(content), suffix_rank, path)

    return sorted(paths, key=sort_key)[0]


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
    class_paths: dict[str, str] = {}
    for path, content in sorted(
        planned.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    ):
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        match = _WIDGET_CLASS_RE.search(content)
        if match is None:
            continue
        class_name = match.group("name")
        if class_name in class_paths:
            continue
        class_paths[class_name] = path
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


def ensure_referenced_widget_imports(planned: dict[str, str]) -> dict[str, str]:
    """Add missing widget imports when screens reference planned ``lib/widgets`` classes."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    package_name = _detect_package_name(planned)
    updated = dict(planned)
    for path, content in planned.items():
        if not path.startswith("lib/features/") or not path.endswith("_screen.dart"):
            continue
        import_ctx = ImportContext(
            package_name=package_name,
            use_package_imports=True,
            source_file=path,
        )
        imports_to_add: list[str] = []
        for class_name, widget_path in sorted(class_paths.items()):
            if not re.search(rf"\b{re.escape(class_name)}\s*\(", content):
                continue
            widget_uri = import_ctx.uri(widget_path.removeprefix("lib/"))
            import_line = f"import '{widget_uri}';"
            if import_line not in content:
                imports_to_add.append(import_line)
        if imports_to_add:
            content = _insert_import_lines(content, imports_to_add)
        content = strip_llm_relative_widget_imports(content)
        content = strip_unused_widget_imports(content, updated)
        content = strip_orphan_widget_imports(content, updated, source_file=path)
        updated[path] = strip_ambiguous_widget_imports(
            content,
            updated,
            source_file=path,
        )
    return updated


def sync_widget_class_constructors(content: str) -> str:
    """Align the primary widget constructor name with the declared widget class."""
    from figma_flutter_agent.generator.dart_postprocess import repair_obsolete_dart_default_colons

    content = repair_obsolete_dart_default_colons(content)
    match = _WIDGET_CLASS_RE.search(content)
    if match is None:
        return content
    class_name = match.group("name")
    class_end = match.end()
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
    if fixed_header == header:
        return content
    return content[:class_end] + fixed_header + content[header_end:]


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
    if header.count("required Key key") > 1:
        return True
    return False


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
    from figma_flutter_agent.generator.dart_postprocess import _split_top_level_commas

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
    from figma_flutter_agent.generator.dart_delimiters import find_balanced_call_close_paren
    from figma_flutter_agent.generator.dart_postprocess import _split_top_level_commas

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
        close_paren = decl_start + semi
        while close_paren > open_paren and header[close_paren] != ")":
            close_paren -= 1
        if close_paren <= open_paren:
            return header
    param_inner = header[open_paren + 1 : close_paren]
    param_chunks: list[str] = []
    if (
        param_inner.count("required Key key") > 1
        or param_inner.count("{") != param_inner.count("}")
    ):
        param_chunks.extend(_split_top_level_commas(re.sub(r"[{}]", "", param_inner)))
    else:
        for brace_match in re.finditer(
            r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
            param_inner,
            flags=re.DOTALL,
        ):
            param_chunks.extend(_split_top_level_commas(brace_match.group(1)))
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
    from figma_flutter_agent.generator.llm_dart import dedupe_primary_widget_class
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


def _sanitize_screen_dart_syntax(content: str) -> str:
    """Remove orphan list commas and repair delimiter drift on screen files."""
    from figma_flutter_agent.generator.llm_dart import repair_dart_delimiters

    lines = [line for line in content.splitlines() if not re.match(r"^\s*,\s*$", line)]
    text = "\n".join(lines)
    text = re.sub(r"\n(\s*);\s*\n(\s*[\]\)])", r"\n\2", text)
    return repair_dart_delimiters(text)


def _balance_planned_widget_delimiters(planned: dict[str, str]) -> dict[str, str]:
    """Repair delimiter drift on planned widget and screen Dart files."""
    from figma_flutter_agent.generator.llm_dart import repair_dart_delimiters

    updated = dict(planned)
    for path, content in planned.items():
        if path.endswith("_screen.dart"):
            repaired = _sanitize_screen_dart_syntax(content)
            if repaired != content:
                updated[path] = repaired
            continue
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        repaired = repair_dart_delimiters(content)
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


def reconcile_planned_dart_files(
    planned: dict[str, str],
    *,
    blocked_asset_paths: frozenset[str] | None = None,
    use_ast_sidecar: bool | None = None,
    typography_tokens: DesignTokens | None = None,
    package_name: str = "demo_app",
) -> dict[str, str]:
    """Apply deterministic reconciliation and postprocess to planned Dart files."""
    from figma_flutter_agent.generator.app_typography_collapse import (
        collapse_inline_text_styles_to_app_typography,
    )

    ast_enabled = _use_ast_sidecar_enabled(use_ast_sidecar)
    ast_backends: set[str] = set()
    updated = reconcile_cluster_variant_args(planned)
    updated = prune_duplicate_widget_classes(updated)
    updated = _dedupe_screen_class_definitions(updated)
    updated = _balance_planned_widget_delimiters(updated)
    updated = ensure_referenced_widget_imports(updated)
    callback_widgets = discover_widgets_requiring_on_pressed(updated)
    blocked = blocked_asset_paths or frozenset()
    for path, content in updated.items():
        if not path.endswith(".dart"):
            continue
        if path.startswith("lib/widgets/"):
            content = sync_widget_class_constructors(content)
        if path.startswith(("lib/", "test/")):
            sanitized = sanitize_dart_blocked_assets(content, blocked)
            include_text_scaler = not (
                path.startswith("lib/generated/") and path.endswith("_layout.dart")
            )
            processed = process_generated_dart_source(
                sanitized,
                include_text_scaler=include_text_scaler,
                use_ast_sidecar=ast_enabled,
            )
            if ast_enabled:
                ast_backends.add("subprocess")
            if callback_widgets and _dart_accepts_on_pressed_call_sites(path):
                processed = ensure_required_on_pressed_callbacks(
                    processed,
                    widget_names=callback_widgets,
                )
                processed = sanitize_named_only_widget_calls(
                    processed,
                    widget_names=callback_widgets,
                )
            if path.endswith("_screen.dart"):
                processed = ensure_screen_stack_paint_order(processed)
                processed = _sanitize_screen_dart_syntax(processed)
            if typography_tokens is not None and path.endswith(".dart"):
                processed = collapse_inline_text_styles_to_app_typography(
                    processed,
                    typography_tokens,
                    package_name=package_name,
                )
            updated[path] = processed
    if ast_enabled and ast_backends:
        logger.info("AST sidecar reconcile backend(s): {}", ", ".join(sorted(ast_backends)))
    return remediate_text_scaler_contract(updated)
