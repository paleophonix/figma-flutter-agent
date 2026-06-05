"""FID-44 spike gate: audit fixtures for P3 / wide-gamut gradient metadata."""

from __future__ import annotations

import json
from pathlib import Path

_FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


def _collect_gradient_nodes(payload: object, hits: list[dict[str, object]]) -> None:
    if isinstance(payload, dict):
        fills = payload.get("fills")
        if isinstance(fills, list):
            for fill in fills:
                if not isinstance(fill, dict) or fill.get("type") != "GRADIENT_LINEAR":
                    continue
                color_space = fill.get("gradientColorSpace") or fill.get("colorSpace")
                if color_space is not None or fill.get("gradientHandlePositions"):
                    hits.append(
                        {
                            "id": payload.get("id"),
                            "colorSpace": color_space,
                            "handlePositions": fill.get("gradientHandlePositions"),
                        }
                    )
        for value in payload.values():
            _collect_gradient_nodes(value, hits)
    elif isinstance(payload, list):
        for item in payload:
            _collect_gradient_nodes(item, hits)


def test_fixture_gradients_have_no_p3_metadata_spike_gate() -> None:
    """No P3 / handle-position gradients in offline fixtures — resample deferred (FID-44)."""
    hits: list[dict[str, object]] = []
    for path in sorted(_FIXTURES_ROOT.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _collect_gradient_nodes(payload, hits)
    assert hits == []
