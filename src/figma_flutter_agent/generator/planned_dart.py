"""Reconcile planned Dart files before analyze and write."""

from __future__ import annotations

import re
from pathlib import Path

from figma_flutter_agent.assets.screen_frame import sanitize_dart_blocked_assets
from figma_flutter_agent.generator.dart_postprocess import (
    discover_widgets_requiring_on_pressed,
    ensure_required_on_pressed_callbacks,
    postprocess_generated_dart,
    strip_named_parameter,
)
from figma_flutter_agent.generator.paths import ImportContext

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
    if fixed_header == header:
        return content
    return content[:class_end] + fixed_header + content[header_end:]


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


def _balance_planned_widget_delimiters(planned: dict[str, str]) -> dict[str, str]:
    """Close missing ``}`` / ``)`` / ``]`` on planned widget files after LLM repair."""
    from figma_flutter_agent.generator.llm_dart import (
        balance_dart_delimiters,
        validate_dart_delimiters,
    )

    updated = dict(planned)
    for path, content in planned.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        if validate_dart_delimiters(content) is None:
            continue
        balanced = balance_dart_delimiters(content)
        if balanced is not None:
            updated[path] = balanced
    return updated


def reconcile_planned_dart_files(
    planned: dict[str, str],
    *,
    blocked_asset_paths: frozenset[str] | None = None,
) -> dict[str, str]:
    """Apply deterministic reconciliation and postprocess to planned Dart files."""
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
            processed = postprocess_generated_dart(
                sanitized,
                include_text_scaler=include_text_scaler,
            )
            if callback_widgets:
                processed = ensure_required_on_pressed_callbacks(
                    processed,
                    widget_names=callback_widgets,
                )
            updated[path] = processed
    return updated
