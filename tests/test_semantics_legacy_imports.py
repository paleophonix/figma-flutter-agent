"""Ensure semantics detectors do not import legacy interaction heuristics."""

from __future__ import annotations

from pathlib import Path

W1_DETECTOR_FILES = (
    "actions.py",
    "inputs.py",
    "display.py",
)


def test_semantics_detectors_do_not_import_interaction() -> None:
    detectors_root = (
        Path(__file__).resolve().parents[1] / "src" / "figma_flutter_agent" / "parser" / "semantics" / "detectors"
    )
    offenders: list[str] = []
    for name in W1_DETECTOR_FILES:
        path = detectors_root / name
        text = path.read_text(encoding="utf-8")
        if "parser.interaction" in text or "from figma_flutter_agent.parser.interaction" in text:
            offenders.append(path.as_posix())
    assert offenders == [], f"legacy interaction imports: {offenders}"
