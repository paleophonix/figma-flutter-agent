"""Tests for demo ``.debug/reference`` emitter golden bundle."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT_CANDIDATES = (
    _REPO_ROOT.parent / "demo_app",
    _REPO_ROOT.parent / "flutter-demo-project" / "demo_app",
)
_FEATURE = "background"
_MALFORMED_STYLE_RE = re.compile(r"copyWith\([^)]*\)\),\s*fontSize")


def _demo_project_dir() -> Path | None:
    for candidate in _DEMO_ROOT_CANDIDATES:
        ref = candidate / ".debug/reference/emitter" / f"{_FEATURE}_screen.dart"
        if ref.is_file():
            return candidate
    return None


@pytest.mark.skipif(_demo_project_dir() is None, reason="demo emitter reference not present")
def test_background_reference_bundle_has_expected_sections() -> None:
    project_dir = _demo_project_dir()
    assert project_dir is not None
    bundle = (project_dir / ".debug/reference/emitter" / f"{_FEATURE}_screen.dart").read_text(
        encoding="utf-8"
    )
    assert bundle.startswith("// EMITTER REFERENCE")
    assert "// --- begin lib/generated/background_layout.dart ---" in bundle
    assert "// --- begin lib/features/background/background_screen.dart ---" in bundle
    assert "const BackgroundLayout()" in bundle
    assert _MALFORMED_STYLE_RE.search(bundle) is None


@pytest.mark.skipif(_demo_project_dir() is None, reason="demo emitter reference not present")
def test_background_reference_metadata_points_at_bundle() -> None:
    project_dir = _demo_project_dir()
    assert project_dir is not None
    meta_path = project_dir / ".debug/reference/emitter" / f"{_FEATURE}_reference.json"
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert payload["bundle"].endswith(f"reference/emitter/{_FEATURE}_screen.dart")
    assert "libLayout" in payload["sources"]
