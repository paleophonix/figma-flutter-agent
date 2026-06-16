"""Infer feature slug from generated Dart paths."""

from __future__ import annotations

import re

_FEATURE_RE = re.compile(
    r"lib/(?:features/([^/]+)(?:/|$)|screens/([^/_]+)(?:_screen)?\.dart)"
)


def infer_feature_slug(written_files: list[str]) -> str | None:
    """Infer feature slug from generated file paths."""
    for path in written_files:
        normalized = path.replace("\\", "/")
        match = _FEATURE_RE.search(normalized)
        if match is None:
            continue
        return match.group(1) or match.group(2)
    return None
