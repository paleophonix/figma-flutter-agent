"""Regression: OpenCode submodule metadata must be present for GitHub and git submodule."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITMODULES = ROOT / ".gitmodules"


def test_opencode_gitmodules_maps_submodule_url() -> None:
    assert GITMODULES.is_file(), "missing .gitmodules — GitHub cannot link src/opencode"
    text = GITMODULES.read_text(encoding="utf-8")
    assert '[submodule "src/opencode"]' in text
    assert "path = src/opencode" in text
    assert "url = https://github.com/anomalyco/opencode.git" in text
