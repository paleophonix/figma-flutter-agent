"""OpenCode CLI preflight checks."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.cli_preflight import (
    OPENCODE_INSTALL_HINT,
    opencode_cli_doctor_detail,
    resolve_opencode_binary,
)


def test_opencode_install_hint_documents_npm_global() -> None:
    assert "opencode-ai" in OPENCODE_INSTALL_HINT


def test_opencode_cli_doctor_detail_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.cli_preflight.shutil.which",
        lambda _name: None,
    )
    ok, detail = opencode_cli_doctor_detail()
    assert not ok
    assert "opencode-ai" in detail


def test_opencode_cli_doctor_detail_when_present(monkeypatch) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.cli_preflight.shutil.which",
        lambda name: "/usr/bin/opencode" if name == "opencode" else None,
    )
    ok, detail = opencode_cli_doctor_detail()
    assert ok
    assert detail.endswith("opencode")
    assert resolve_opencode_binary() == "/usr/bin/opencode"
