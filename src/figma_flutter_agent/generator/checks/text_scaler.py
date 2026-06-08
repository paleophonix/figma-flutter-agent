"""textScaler contracts and remediation for generated Dart sources."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.postprocess import (
    TEXT_DISPLAY_WIDGET_RE,
    ensure_text_scaler_support,
    inline_orphan_text_scaler_refs,
    strip_const_runtime_text_scaler,
)

TEXT_SCALER_RE = re.compile(
    r"(textScaler:\s*MediaQuery\.textScalerOf\(\w+\)|"
    r"(?:final|var)\s+\w*\s*textScaler\s*=\s*MediaQuery\.textScalerOf\(\w+\))"
)

_UI_DART_PREFIXES = ("lib/features/", "lib/presentation/", "lib/widgets/")


def dart_path_needs_text_scaler_contract(path: str) -> bool:
    if not path.endswith(".dart"):
        return False
    if not path.startswith(_UI_DART_PREFIXES):
        return False
    return not (path.startswith("lib/generated/") and path.endswith("_layout.dart"))


def source_satisfies_text_scaler_contract(content: str) -> bool:
    if not TEXT_DISPLAY_WIDGET_RE.search(content):
        return True
    return TEXT_SCALER_RE.search(content) is not None


def text_scaler_missing_paths(ui_dart_sources: dict[str, str]) -> list[str]:
    return [
        path
        for path, content in ui_dart_sources.items()
        if TEXT_DISPLAY_WIDGET_RE.search(content) and not TEXT_SCALER_RE.search(content)
    ]


def remediate_text_scaler_contract(planned_files: dict[str, str]) -> dict[str, str]:
    """Ensure UI Dart sources satisfy the textScaler contract after layout splice."""
    updated = dict(planned_files)
    for path, content in planned_files.items():
        if not dart_path_needs_text_scaler_contract(path):
            continue
        if source_satisfies_text_scaler_contract(content):
            continue
        fixed = ensure_text_scaler_support(content)
        if not source_satisfies_text_scaler_contract(fixed):
            fixed = inline_orphan_text_scaler_refs(fixed)
        fixed = strip_const_runtime_text_scaler(fixed)
        updated[path] = fixed
    return updated
