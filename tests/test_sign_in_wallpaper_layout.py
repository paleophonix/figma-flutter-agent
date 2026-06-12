"""Sign-in classic layout: wallpaper visible, social button labels centered."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import CleanDesignTreeNode

_DEMO_DUMP = (
    Path(__file__).resolve().parents[2].parent
    / "demo_app"
    / ".debug"
    / "processed"
    / "sign_in_layout.json"
)


def _load_demo_tree() -> CleanDesignTreeNode | None:
    if not _DEMO_DUMP.is_file():
        return None
    payload = json.loads(_DEMO_DUMP.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(payload["cleanTree"])


@pytest.mark.skipif(_load_demo_tree() is None, reason="demo processed dump not present")
def test_sign_in_wallpaper_not_covered_by_opaque_foreground() -> None:
    tree = _load_demo_tree()
    assert tree is not None
    layout = render_layout_file(tree, feature_name="sign_in", uses_svg=True)[
        "lib/generated/sign_in_layout.dart"
    ]
    assert "group_6800_1_3572.svg" in layout
    assert "vector_1_3571.svg" in layout
    assert layout.index("Positioned.fill") < layout.index("Welcome Back")
    assert "BoxDecoration(color: Color(0xFFFFFFFF)), child: Stack" not in layout
    assert "BoxFit.cover" in layout
    assert "figma-1_3603" in layout


@pytest.mark.skipif(_load_demo_tree() is None, reason="demo processed dump not present")
def test_sign_in_back_arrow_not_pi_flipped() -> None:
    tree = _load_demo_tree()
    assert tree is not None
    layout = render_layout_file(tree, feature_name="sign_in", uses_svg=True)[
        "lib/generated/sign_in_layout.dart"
    ]
    assert "vector_1_3607.svg" in layout
    assert "Transform.rotate(angle: -3.14" not in layout


@pytest.mark.skipif(_load_demo_tree() is None, reason="demo processed dump not present")
def test_google_icon_vertically_centered_in_auth_pill() -> None:
    tree = _load_demo_tree()
    assert tree is not None
    layout = render_layout_file(tree, feature_name="sign_in", uses_svg=True)[
        "lib/generated/sign_in_layout.dart"
    ]
    google_idx = layout.index("figma-1_3594")
    window = layout[max(0, google_idx - 120) : google_idx + 40]
    assert "top: 19.5" in window or "top: 19.0" in window


@pytest.mark.skipif(_load_demo_tree() is None, reason="demo processed dump not present")
def test_facebook_label_vertically_centered_in_button() -> None:
    tree = _load_demo_tree()
    assert tree is not None
    layout = render_layout_file(tree, feature_name="sign_in", uses_svg=True)[
        "lib/generated/sign_in_layout.dart"
    ]
    facebook_idx = layout.index("CONTINUE WITH FACEBOOK")
    window = layout[max(0, facebook_idx - 500) : facebook_idx + 120]
    assert "Alignment.center" in window
    assert "top: 13.0" not in window or "height: 63.0" in window
