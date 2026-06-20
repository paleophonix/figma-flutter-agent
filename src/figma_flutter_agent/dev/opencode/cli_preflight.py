"""OpenCode CLI availability checks for doctor and bootstrap."""

from __future__ import annotations

import shutil

OPENCODE_INSTALL_HINT = "npm install -g opencode-ai"


def resolve_opencode_binary() -> str | None:
    """Return ``opencode`` executable path when present on PATH."""
    return shutil.which("opencode")


def opencode_cli_doctor_detail() -> tuple[bool, str]:
    """Return doctor ok flag and detail string for OpenCode CLI."""
    path = resolve_opencode_binary()
    if path:
        return True, path
    return False, f"not on PATH — {OPENCODE_INSTALL_HINT}"
