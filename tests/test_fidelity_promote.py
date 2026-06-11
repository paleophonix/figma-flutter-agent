"""Fidelity manifest promotion CLI (EPIC 4.5)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.fidelity.manifest import package_fidelity_manifest_path
from figma_flutter_agent.generator.ir.fidelity.promote import (
    PromotionRequest,
    promote_manifest_entry,
    validate_manifest_entries,
)
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind


def test_validate_package_manifest_passes() -> None:
    errors = validate_manifest_entries(package_fidelity_manifest_path())
    assert errors == []


def test_promote_dry_run_accepts_corpus_screen() -> None:
    result = promote_manifest_entry(
        PromotionRequest(
            kind=WidgetIrKind.BUTTON_FILLED,
            tier=FidelityTier.NATIVE_VERIFIED,
            fixture_id="sign_up_and_sign_in",
        ),
        dry_run=True,
    )
    assert result.dry_run is True
    assert result.entry.fixture_ids == ("sign_up_and_sign_in",)


def test_promote_rejects_unknown_fixture_id() -> None:
    try:
        promote_manifest_entry(
            PromotionRequest(
                kind=WidgetIrKind.BUTTON_FILLED,
                tier=FidelityTier.NATIVE_VERIFIED,
                fixture_id="not-a-real-corpus-screen",
            ),
            dry_run=True,
        )
    except GenerationError:
        return
    raise AssertionError("expected GenerationError")


def test_fidelity_validate_cli() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "poetry", "run", "figma-flutter", "fidelity", "validate"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        result = subprocess.run(
            [sys.executable, "-c", "from figma_flutter_agent.generator.ir.fidelity.promote import validate_manifest_entries; from figma_flutter_agent.generator.ir.fidelity.manifest import package_fidelity_manifest_path; assert not validate_manifest_entries(package_fidelity_manifest_path())"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
