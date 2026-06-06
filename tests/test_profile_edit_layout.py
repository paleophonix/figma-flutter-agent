"""Profile edit (phone artboard) layout matches spec §7.3 and reference UX."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.tree import build_clean_tree

_DUMP_CANDIDATES = (
    Path(r"e:/@dev/flutter-demo-project/ataev/.figma_debug/raw/profile_edit_layout.json"),
    Path(r"e:/@dev/flutter-demo-project/demo_app/.figma_debug/raw/background_layout.json"),
)


def _profile_edit_layout() -> str:
    dump = next((path for path in _DUMP_CANDIDATES if path.is_file()), None)
    if dump is None:
        pytest.skip("profile_edit Figma dump not available on this machine")
    raw = json.loads(dump.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(raw)
    root = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=dump.parent.parent.parent,
    )
    planned = render_layout_file(
        root,
        feature_name="profile_edit",
        uses_svg=True,
        use_geometry_planner=True,
        responsive_enabled=True,
    )
    return planned["lib/generated/profile_edit_layout.dart"]


def test_profile_edit_emits_form_controls_and_primary_cta() -> None:
    layout = _profile_edit_layout()
    assert "TextField" in layout
    assert "28A745" in layout
    assert "Сохранить изменения" in layout
    assert "BorderRadius.only" in layout


def test_profile_edit_skips_dead_wide_reflow_on_phone_artboard() -> None:
    layout = _profile_edit_layout()
    assert "clamp(0.0, 390.0)" not in layout
    assert layout.count("isWideLayout") == 0


def test_profile_edit_stretches_content_on_wide_host() -> None:
    layout = _profile_edit_layout()
    assert "width: constraints.maxWidth" in layout
    assert "Container(width: 390.0" not in layout
    assert "SizedBox(width: 390, height: 844" not in layout
    assert "SizedBox(width: 390.0" not in layout
    assert "Container(width: 357.0" not in layout
    assert "Positioned(left: 0.0, bottom: 0.0, width: 390.0" not in layout
    assert "bottom: 0.0, height: 170.0, right: 0.0" in layout
