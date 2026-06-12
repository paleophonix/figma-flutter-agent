"""Debug Dart snapshot paths (plan / final / bug)."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.debug.paths import dart_debug_snapshot_path


def test_dart_debug_snapshot_paths(tmp_path: Path) -> None:
    project = tmp_path / "demo_app2"
    assert dart_debug_snapshot_path(project, "sign_in", "plan") == (
        project / ".debug" / "dart" / "sign_in_plan.dart"
    )
    assert dart_debug_snapshot_path(project, "sign_in", "final") == (
        project / ".debug" / "dart" / "sign_in_screen.dart"
    )
    assert dart_debug_snapshot_path(project, "sign_in", "bug") == (
        project / ".debug" / "dart.bug" / "sign_in_screen.dart"
    )


def test_dart_debug_snapshot_path_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown dart debug snapshot"):
        dart_debug_snapshot_path(Path("."), "x", "nope")
