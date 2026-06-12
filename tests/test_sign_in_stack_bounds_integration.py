"""Integration: stack bounds fix on real sign_in artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.dart.llm_codegen import (
    fix_invalid_positioned_constraints,
    fix_positioned_stack_bounds_from_tree,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

_DEMO_APP = Path(__file__).resolve().parents[2].parent / "demo_app"


def test_fix_sign_in_google_button_positioned_bounds() -> None:
    dump_path = _DEMO_APP / ".debug" / "processed" / "sign_in_layout.json"
    screen_path = _DEMO_APP / "lib" / "features" / "sign_in" / "sign_in_screen.dart"
    if not dump_path.is_file() or not screen_path.is_file():
        return

    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    tree = CleanDesignTreeNode.model_validate(payload["cleanTree"])
    code = screen_path.read_text(encoding="utf-8")
    anchor = code.find("figma-1:3590")
    assert anchor != -1

    fixed = fix_invalid_positioned_constraints(fix_positioned_stack_bounds_from_tree(code, tree))
    google_region = fixed[fixed.rfind("Positioned(", 0, anchor) : anchor + 80]
    assert "width: 374" in google_region
    assert "height: 63" in google_region
