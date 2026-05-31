"""Reconcile planned Dart files before analyze and write."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from pathlib import Path

from figma_flutter_agent.assets.screen_frame import sanitize_dart_blocked_assets
from figma_flutter_agent.config import Settings
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens
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
_LARGE_PLANNED_DART_BYTES = 80_000
_MAX_WIDGET_CONSTRUCTOR_PARAM_CHARS = 2000
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


def _normalized_widget_stem(stem: str) -> str:
    from figma_flutter_agent.generator.layout_common import to_pascal_case, to_snake_case

    return to_snake_case(to_pascal_case(stem))


def _widget_build_snippet(content: str, *, max_chars: int = 1200) -> str:
    match = re.search(r"@override\s+Widget\s+build\s*\([^)]*\)", content)
    if match is None:
        match = re.search(r"Widget\s+build\s*\([^)]*\)", content)
    if match is None:
        return content[:max_chars]
    start = match.end()
    return content[start : start + max_chars]


def _is_self_referential_widget_build(content: str, class_name: str) -> bool:
    if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", content):
        return False
    build = _widget_build_snippet(content)
    if re.search(
        rf"return\s+(?:const\s+)?{re.escape(class_name)}\s*\([^;{{]*\)\s*;",
        build,
    ):
        return True
    return bool(re.search(r"return\s+context\.widget\b", build))


def _pick_canonical_widget_path(paths: list[str], planned: dict[str, str]) -> str:
    def sort_key(path: str) -> tuple[int, int, int, str]:
        content = planned.get(path, "")
        class_match = _WIDGET_CLASS_RE.search(content)
        class_name = class_match.group("name") if class_match else ""
        self_ref_rank = 1 if _is_self_referential_widget_build(content, class_name) else 0
        shrink_rank = 1 if _is_shrink_only_widget_source(content) else 0
        stem = Path(path).stem
        from figma_flutter_agent.generator.layout_common import to_snake_case

        expected_stem = to_snake_case(class_name) if class_name else stem
        stem_match_rank = 0 if _normalized_widget_stem(stem) == expected_stem else 1
        suffix_match = re.search(r"_(\d+)$", stem)
        suffix_rank = int(suffix_match.group(1)) if suffix_match else 0
        return (self_ref_rank, shrink_rank, stem_match_rank, -len(content), suffix_rank, path)

    return sorted(paths, key=sort_key)[0]


def preferred_widget_path_for_class(class_name: str) -> str:
    from figma_flutter_agent.generator.layout_common import to_snake_case

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


def _skips_codegen_ast_pass(normalized_path: str, sanitized: str) -> bool:
    if _is_deterministic_widget_path(normalized_path):
        return True
    if normalized_path.startswith(("lib/generated/", "lib/theme/")):
        return True
    if normalized_path.endswith("_screen.dart") and _screen_is_layout_delegate(sanitized):
        return True
    return False


def _screen_is_layout_delegate(screen_source: str) -> bool:
    if "Stack(" in screen_source or "Positioned(" in screen_source:
        return False
    return bool(re.search(r"const\s+\w+Layout\s*\(\s*\)", screen_source))


def _is_large_planned_dart(content: str) -> bool:
    return len(content.encode("utf-8")) > _LARGE_PLANNED_DART_BYTES


def _path_skips_ast_reconcile(normalized_path: str) -> bool:
    if normalized_path.startswith("lib/widgets/"):
        return True
    if normalized_path.startswith(("lib/theme/", "lib/generated/")):
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


def _sanitize_ingested_widget_source(source: str) -> str:
    """Lightweight sanitize for on-disk / renderer-produced widget bodies (no AST)."""
    from figma_flutter_agent.generator.dart_syntax_repairs import (
        apply_llm_dart_syntax_repairs,
        sanitize_planned_widget_syntax,
    )

    return sanitize_planned_widget_syntax(apply_llm_dart_syntax_repairs(source))


def _widget_body_needs_recovery(content: str, class_name: str) -> bool:
    if _is_self_referential_widget_build(content, class_name):
        return True
    if len(content) > 500 and "Stack(" in content:
        return False
    if "SvgPicture.asset" in content or "Positioned(" in content:
        return False
    return True


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

    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

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
            if existing is not None and not _is_shrink_only_widget_source(existing):
                continue
            disk_path = project_dir / widget_rel
            if not disk_path.is_file():
                continue
            disk_source = disk_path.read_text(encoding="utf-8")
            if _is_shrink_only_widget_source(disk_source):
                continue
            from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

            disk_source = _sanitize_ingested_widget_source(disk_source)
            if validate_dart_delimiters(disk_source) is not None:
                logger.warning(
                    "Skipping hydrate {} from disk: invalid Dart after sanitize",
                    widget_rel,
                )
                continue
            updated[widget_rel] = disk_source
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
    from figma_flutter_agent.generator.llm_dart import _safe_strip_widget_class_definition

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


def repair_self_referential_widget_builds(planned: dict[str, str]) -> dict[str, str]:
    """Drop or neutralize widget files whose ``build`` only instantiates their own class."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    updated = dict(planned)
    for class_name, paths in _group_paths_by_class(planned).items():
        if len(paths) < 2:
            path = paths[0]
            content = updated.get(path, "")
            if _is_self_referential_widget_build(content, class_name):
                updated.pop(path, None)
            continue
        canonical = _pick_canonical_widget_path(paths, updated)
        for path in paths:
            if path == canonical:
                continue
            content = updated.get(path, "")
            if _is_self_referential_widget_build(content, class_name):
                updated.pop(path, None)
    return updated


def _group_paths_by_class(planned: dict[str, str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path, class_name in _widget_class_names_by_path(planned).items():
        grouped.setdefault(class_name, []).append(path)
    return grouped


def _replace_self_referential_build(content: str, class_name: str) -> str:
    patched = re.sub(
        rf"return\s+(?:const\s+)?{re.escape(class_name)}\s*\([^)]*\)\s*;",
        "return const SizedBox.shrink();",
        content,
        count=1,
    )
    if patched != content:
        return patched
    return re.sub(
        r"return\s+context\.widget\s*;",
        "return const SizedBox.shrink();",
        content,
        count=1,
    )


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
    return normalized.startswith("lib/generated/") and normalized.endswith("_layout.dart")


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
        normalized = path.replace("\\", "/")
        if normalized.endswith("_layout.dart") and _is_large_planned_dart(content):
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
) -> dict[str, str]:
    """Refresh write payloads and pull in layout/screen when widget imports were reconciled."""
    if not planned_files:
        return dict(files_to_write)

    synced = sync_widget_consumer_imports(planned_files)
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
    from figma_flutter_agent.generator.layout_common import to_pascal_case

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
    from figma_flutter_agent.generator.layout_common import to_pascal_case
    from figma_flutter_agent.generator.subtree_widgets import _rename_widget_class

    updated = dict(planned)
    for path, content in planned.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        expected = to_pascal_case(Path(path).stem)
        match = _WIDGET_CLASS_RE.search(content)
        if match is None:
            continue
        actual = match.group("name")
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
            match = _WIDGET_CLASS_RE.search(content)
            if match is not None:
                own_class = match.group("name")
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
        base = class_name[: suffix_match.start()]
        suffix = suffix_match.group(1)
        pattern = rf"\b{re.escape(base)}(?!{re.escape(suffix)})\s*\("
    else:
        pattern = rf"\b{re.escape(class_name)}\d+\s*\("
    patched = re.sub(pattern, f"{class_name}(", body)
    if patched == body:
        return content
    return content[:start] + patched


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
    if len(param_inner) > _MAX_WIDGET_CONSTRUCTOR_PARAM_CHARS:
        logger.warning(
            "Skipping widget constructor repair for {} ({} param chars)",
            class_name,
            len(param_inner),
        )
        return header
    param_chunks: list[str] = []
    if (
        param_inner.count("required Key key") > 1
        or param_inner.count("{") != param_inner.count("}")
    ):
        param_chunks.extend(_split_top_level_commas(re.sub(r"[{}]", "", param_inner)))
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
    """Repair delimiter drift on screen files via the AST sidecar."""
    from figma_flutter_agent.generator.dart_syntax_repairs import (
        apply_planned_delimiter_balance,
    )

    return apply_planned_delimiter_balance(content)


def _sanitize_widget_dart_syntax(content: str) -> str:
    from figma_flutter_agent.generator.dart_syntax_repairs import sanitize_planned_widget_syntax

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
    from figma_flutter_agent.generator.dart_syntax_repairs import (
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


def repair_planned_format_parse_failures(
    planned: dict[str, str],
    format_paths: tuple[str, ...],
    *,
    analyze_errors: tuple[str, ...] = (),
) -> dict[str, str]:
    """Deterministic cleanup when ``dart format`` cannot parse planned Dart (e.g. ``])))}}``)."""
    if not format_paths:
        return planned
    from figma_flutter_agent.generator.dart_syntax_repairs import (
        is_garbage_closer_only_line,
        is_orphan_semicolon_line,
        parse_format_error_line_numbers,
        strip_garbage_closer_only_lines,
        strip_orphan_semicolon_only_lines,
    )
    from figma_flutter_agent.generator.llm_dart import repair_dart_delimiters

    error_lines = parse_format_error_line_numbers(analyze_errors)
    updated = dict(planned)
    for path in format_paths:
        normalized = path.replace("\\", "/")
        content = planned.get(normalized) or planned.get(path)
        if content is None:
            continue
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
        repaired = _sanitize_planned_dart_syntax(normalized, text)
        if repaired != content:
            updated[normalized] = repaired
    return updated


def _balance_planned_widget_delimiters(planned: dict[str, str]) -> dict[str, str]:
    """Repair delimiter drift on planned widget and screen Dart files (AST sidecar)."""
    from figma_flutter_agent.generator.dart_syntax_repairs import (
        apply_planned_delimiter_balance,
    )

    updated = dict(planned)
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart"):
            continue
        if normalized.startswith("lib/widgets/") and len(content) > 200_000:
            continue
        repaired = apply_planned_delimiter_balance(content)
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
    clean_tree: CleanDesignTreeNode | None = None,
    ast_full_reconcile_paths: frozenset[str] | None = None,
    incremental: bool | None = None,
    project_dir: Path | None = None,
    widget_suffix: str | None = None,
    uses_svg: bool | None = None,
    use_package_imports: bool = True,
) -> dict[str, str]:
    """Apply deterministic reconciliation and postprocess to planned Dart files."""
    from figma_flutter_agent.generator.app_typography_collapse import (
        collapse_inline_text_styles_to_app_typography,
    )

    ast_enabled = _use_ast_sidecar_enabled(use_ast_sidecar)
    ast_backends: set[str] = set()
    updated = dict(planned)
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
    _log_reconcile_phase("consolidate_widgets", end=True)
    if not incremental and _any_widget_needs_disk_recovery(updated):
        _log_reconcile_phase("hydrate_absorb")
        updated = hydrate_planned_widget_files_from_project(updated, project_dir)
        updated = absorb_disk_widget_alias_bodies(updated, project_dir)
        _log_reconcile_phase("hydrate_absorb", end=True)
        updated = prune_duplicate_widget_classes(updated)
        updated = repair_self_referential_widget_builds(updated)
    elif not incremental:
        logger.info("Planned reconcile: skipping hydrate/absorb (widgets already complete)")
    if not incremental and clean_tree is not None and widget_suffix:
        from figma_flutter_agent.generator.subtree_widgets import (
            refresh_subtree_widget_planned_files,
            _collect_subtree_specs_to_render,
            collect_subtree_widget_specs,
            _layout_widget_class_names,
        )

        specs = list(
            collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
        )
        layout_names = sorted(_layout_widget_class_names(updated))
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
            from figma_flutter_agent.generator.dart_syntax_repairs import (
                strip_duplicate_key_after_super,
            )

            content = strip_duplicate_key_after_super(content)
        if path.startswith(("lib/", "test/")):
            sanitized = sanitize_dart_blocked_assets(content, blocked)
            include_text_scaler = not (
                path.startswith("lib/generated/") and path.endswith("_layout.dart")
            )
            normalized_path = path.replace("\\", "/")
            run_full_ast = ast_enabled and normalized_path in effective_ast_paths
            if run_full_ast:
                file_started = time.monotonic()
                skip_ast = _skips_codegen_ast_pass(normalized_path, sanitized)
                if skip_ast:
                    processed = _sanitize_ingested_widget_source(sanitized)
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
                from figma_flutter_agent.generator.dart_syntax_repairs import (
                    apply_llm_dart_syntax_repairs,
                )

                processed = apply_llm_dart_syntax_repairs(sanitized)
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
                from figma_flutter_agent.generator.llm_dart import (
                    apply_clean_tree_text_to_screen,
                    apply_safe_screen_code_patch,
                )

                processed = apply_safe_screen_code_patch(
                    processed,
                    ensure_screen_stack_paint_order,
                    label="screen stack paint order",
                )
                if clean_tree is not None:
                    from figma_flutter_agent.generator.layout_flex_reconcile import (
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
    for path, content in list(updated.items()):
        if not path.endswith(".dart"):
            continue
        sanitized = _sanitize_planned_dart_syntax(path, content)
        if sanitized != content:
            updated[path] = sanitized
    if ast_enabled:
        if ast_backends:
            logger.info("AST sidecar reconcile backend(s): {}", ", ".join(sorted(ast_backends)))
        logger.info("Planned Dart reconcile finished in {:.1f}s", time.monotonic() - ast_started)
    return remediate_text_scaler_contract(updated)
