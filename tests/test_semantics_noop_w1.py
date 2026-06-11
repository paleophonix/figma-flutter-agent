"""Semantic no-op oracle for W1 positive fixtures (E6.8 subset)."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.screen import emit_screen_code_from_ir
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.parser.semantics.corpus import load_fixture_payload, load_tree_fixture
from figma_flutter_agent.parser.semantics.metrics import load_w1_manifest

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "layouts" / "semantics"


def _w1_positive_paths() -> list[Path]:
    manifest = load_w1_manifest()
    return list(manifest.positive_paths)


@pytest.mark.parametrize(
    "fixture_path",
    _w1_positive_paths(),
    ids=lambda p: p.relative_to(FIXTURE_ROOT).as_posix(),
)
def test_w1_report_only_emit_noop(fixture_path: Path) -> None:
    payload = load_fixture_payload(fixture_path)
    clean = load_tree_fixture(fixture_path)
    auto_ir = default_screen_ir(clean)
    classified_ir, _ = classify_screen_ir(auto_ir, clean)
    ctx = IrEmitContext(semantic_report_only=True, uses_svg=False, responsive_enabled=False)
    dart_auto = emit_screen_code_from_ir(
        auto_ir,
        clean_tree=clean,
        screen_class="W1NoopScreen",
        ctx=ctx,
        use_scaffold=False,
    )
    dart_classified = emit_screen_code_from_ir(
        classified_ir,
        clean_tree=clean,
        screen_class="W1NoopScreen",
        ctx=ctx,
        use_scaffold=False,
    )
    assert dart_classified == dart_auto, payload.get("expected_kind")
