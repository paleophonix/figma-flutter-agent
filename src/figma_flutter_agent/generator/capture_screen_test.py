"""Canonical visual-refine capture tests (``test/capture/*``)."""

from __future__ import annotations

import re
from collections.abc import Mapping

_CAPTURE_TEST_PATH_RE = re.compile(
    r"^test/capture/(?P<feature>.+)_screen_capture_test\.dart$"
)
_SURFACE_SIZE_RE = re.compile(r"const Size\((\d+),\s*(\d+)\)")
_SCREEN_CLASS_RE = re.compile(
    r"child:\s*(?P<screen>\w+)|collectFigmaKeyBounds\((?P<bounds>\w+)\)"
)
_CLASS_NAME_RE = re.compile(r"class\s+(?P<name>\w+Screen)\b")
_DART_UI_IMAGE_BYTE_FORMAT_IMPORT = "import 'dart:ui' show ImageByteFormat;"
_DART_UI_IMPORT_RE = re.compile(
    r"import\s+['\"]dart:ui['\"](\s+show\s+[^;]*\bImageByteFormat\b[^;]*)?;"
)


def is_capture_screen_test_path(path: str) -> bool:
    return _CAPTURE_TEST_PATH_RE.match(path.replace("\\", "/")) is not None


def repair_capture_screen_test_imports(content: str) -> str:
    """Ensure ``ImageByteFormat`` has a visible import after AST/import stripping."""
    if "ImageByteFormat" not in content and "ui.ImageByteFormat" not in content:
        return content
    if _DART_UI_IMPORT_RE.search(content):
        return content.replace("ui.ImageByteFormat", "ImageByteFormat")

    lines = content.splitlines()
    insert_at = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import "):
            insert_at = index + 1
        elif stripped and not stripped.startswith("//"):
            break
    lines.insert(insert_at, _DART_UI_IMAGE_BYTE_FORMAT_IMPORT)
    repaired = "\n".join(lines)
    if content.endswith("\n") and not repaired.endswith("\n"):
        repaired += "\n"
    return repaired.replace("ui.ImageByteFormat", "ImageByteFormat")


def _infer_screen_class(planned: Mapping[str, str], feature: str) -> str:
    screen_path = f"lib/features/{feature}/{feature}_screen.dart"
    screen_source = planned.get(screen_path, "")
    match = _CLASS_NAME_RE.search(screen_source)
    if match is not None:
        return match.group("name")
    from figma_flutter_agent.generator.layout_common import to_pascal_case

    return f"{to_pascal_case(feature)}Screen"


def _infer_surface_size(capture_source: str, *, default: tuple[int, int] = (390, 844)) -> tuple[int, int]:
    match = _SURFACE_SIZE_RE.search(capture_source)
    if match is None:
        return default
    return int(match.group(1)), int(match.group(2))


def _infer_max_web_width(planned: Mapping[str, str], *, default: int = 1200) -> int:
    for content in planned.values():
        match = re.search(r"maxWebWidth:\s*(\d+)", content)
        if match is not None:
            return int(match.group(1))
    return default


def refresh_capture_tests_in_planned(
    planned: dict[str, str],
    *,
    package_name: str,
    max_web_width: int | None = None,
) -> dict[str, str]:
    """Re-emit capture tests from the Jinja template so analyze always sees valid imports."""
    from figma_flutter_agent.generator.renderer import DartRenderer

    renderer = DartRenderer()
    resolved_max_web = (
        max_web_width
        if max_web_width is not None
        else _infer_max_web_width(planned)
    )
    updated = dict(planned)
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        match = _CAPTURE_TEST_PATH_RE.match(normalized)
        if match is None:
            continue
        feature = match.group("feature")
        width, height = _infer_surface_size(content)
        collect_keys = "UIGeometryMapper" in content
        fresh = renderer.render_capture_test(
            feature_name=feature,
            screen_class=_infer_screen_class(planned, feature),
            package_name=package_name,
            surface_width=width,
            surface_height=height,
            max_web_width=resolved_max_web,
            collect_figma_keys=collect_keys,
        )
        updated[path] = fresh[normalized]
    return updated


def finalize_capture_screen_test_content(content: str) -> str:
    """Last-mile guard before writing capture tests to disk."""
    return repair_capture_screen_test_imports(content)
