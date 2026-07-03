"""Pilot-5 semantic evidence spec lint tests (Program 03 P0-2)."""

from __future__ import annotations

from pathlib import Path

import yaml

from figma_flutter_agent.schemas import WidgetIrKind

EVIDENCE_DIR = Path(__file__).resolve().parent / "fixtures" / "layouts" / "semantics" / "evidence"
SEMANTICS_ROOT = EVIDENCE_DIR.parent

PILOT_FILES = (
    "chip_choice.yaml",
    "button.yaml",
    "nav.yaml",
    "checkbox.yaml",
    "input.yaml",
)


def test_pilot_five_evidence_specs_exist() -> None:
    assert len(PILOT_FILES) == 5
    for name in PILOT_FILES:
        assert (EVIDENCE_DIR / name).is_file()


def test_evidence_specs_reference_existing_fixtures() -> None:
    for name in PILOT_FILES:
        spec = yaml.safe_load((EVIDENCE_DIR / name).read_text(encoding="utf-8"))
        for key in ("fixture_positive", "fixture_negative"):
            for rel in spec.get(key, []):
                assert (SEMANTICS_ROOT / rel).is_file(), f"{name}: missing {rel}"


def test_evidence_specs_declare_non_authoritative_name_text() -> None:
    for name in PILOT_FILES:
        spec = yaml.safe_load((EVIDENCE_DIR / name).read_text(encoding="utf-8"))
        signals = spec.get("supporting_signals", {})
        assert signals.get("name_tokens") == "non_authoritative"
        assert "required_hits" in spec and spec["required_hits"]
        assert "veto_hits" in spec and spec["veto_hits"]


def test_evidence_ir_kinds_are_valid_enum_values() -> None:
    members = set(WidgetIrKind.__members__)
    for name in PILOT_FILES:
        spec = yaml.safe_load((EVIDENCE_DIR / name).read_text(encoding="utf-8"))
        for kind in spec.get("ir_kinds", []):
            assert kind in members, f"{name}: unknown kind {kind}"
