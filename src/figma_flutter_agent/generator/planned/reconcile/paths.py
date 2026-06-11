"""Path predicates and canonicalization."""

from __future__ import annotations

import re
from collections.abc import Mapping

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.dart.package_name import (
    infer_project_package_name_from_sources,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.tools.ast_sidecar import AST_SIDECAR_MAX_SOURCE_BYTES

_LARGE_PLANNED_DART_BYTES = AST_SIDECAR_MAX_SOURCE_BYTES
_PACKAGE_IMPORT_RE = re.compile(r"^import\s+'package:(?P<package>[^/]+)/")
_SDK_PACKAGE_NAMES = frozenset(
    {
        "auto_route",
        "cupertino_icons",
        "flutter",
        "flutter_bloc",
        "flutter_riverpod",
        "flutter_svg",
        "go_router",
        "meta",
        "provider",
        "riverpod",
    }
)


def _detect_package_name(planned: dict[str, str]) -> str:
    return infer_project_package_name_from_sources(list(planned.values()))


def _normalized_widget_stem(stem: str) -> str:
    from figma_flutter_agent.generator.layout.common import to_pascal_case, to_snake_case

    return to_snake_case(to_pascal_case(stem))


def _is_deterministic_widget_path(normalized_path: str) -> bool:
    return normalized_path.startswith("lib/widgets/")


def _is_generated_layout_path(normalized_path: str) -> bool:
    return normalized_path.startswith("lib/generated/") and normalized_path.endswith("_layout.dart")


def _skips_codegen_ast_pass(normalized_path: str, sanitized: str) -> bool:
    from .delegate import _screen_is_layout_delegate

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


def _is_widget_consumer_entry_path(normalized_path: str) -> bool:
    if normalized_path.startswith("lib/features/") and normalized_path.endswith("_screen.dart"):
        return True
    if not normalized_path.startswith("lib/generated/"):
        return False
    return normalized_path.endswith("_layout.dart") or "_chunk_" in normalized_path


def preferred_widget_path_for_class(class_name: str) -> str:
    from figma_flutter_agent.generator.layout.common import to_snake_case

    return f"lib/widgets/{to_snake_case(class_name)}.dart"


def _widget_lib_path_for_class(class_name: str) -> str:
    return preferred_widget_path_for_class(class_name)


def canonicalize_planned_path_keys(planned: dict[str, str]) -> None:
    """Use forward-slash keys so format-gate repairs hit the same entries on Windows."""
    from .bootstrap_refresh import is_agent_generated_bootstrap

    for path in list(planned):
        normalized = path.replace("\\", "/")
        if normalized == path:
            continue
        incoming = planned[path]
        if normalized in planned:
            existing = planned[normalized]
            if is_agent_generated_bootstrap(existing) and not is_agent_generated_bootstrap(
                incoming
            ):
                planned.pop(path)
                continue
            planned[normalized] = incoming
            planned.pop(path)
        else:
            planned[normalized] = planned.pop(path)


def _is_large_planned_dart(content: str) -> bool:
    return len(content.encode("utf-8")) > _LARGE_PLANNED_DART_BYTES


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


def _tree_has_layout_slots(root: CleanDesignTreeNode) -> bool:
    stack = [root]
    while stack:
        node = stack.pop()
        if node.layout_slot is not None:
            return True
        stack.extend(node.children)
    return False


def drop_planned_path_aliases(planned: dict[str, str], normalized_path: str) -> None:
    """Remove duplicate planned keys that differ only by path separators."""
    target = normalized_path.replace("\\", "/")
    for key in list(planned.keys()):
        if key.replace("\\", "/") == target and key != target:
            planned.pop(key, None)


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
