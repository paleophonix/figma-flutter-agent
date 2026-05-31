"""Incremental flutter pub get policy."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.codegen import run_pub_get
from figma_flutter_agent.generator.pub_get_policy import (
    mark_pubspec_resolved,
    needs_pub_get,
    pubspec_digest,
    read_pubspec_resolve_stamp,
)


def test_needs_pub_get_when_stamp_missing(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    assert needs_pub_get(tmp_path) is True


def test_needs_pub_get_false_when_stamp_matches(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / ".dart_tool").mkdir()
    (tmp_path / ".dart_tool" / "package_config.json").write_text("{}", encoding="utf-8")
    mark_pubspec_resolved(tmp_path)
    assert needs_pub_get(tmp_path) is False


def test_needs_pub_get_true_when_pubspec_changed_flag(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    mark_pubspec_resolved(tmp_path)
    assert needs_pub_get(tmp_path, pubspec_changed=True) is True


def test_needs_pub_get_false_when_pubspec_unchanged_flag(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    assert needs_pub_get(tmp_path, pubspec_changed=False) is False


def test_run_pub_get_skips_when_unchanged(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / ".dart_tool").mkdir()
    (tmp_path / ".dart_tool" / "package_config.json").write_text("{}", encoding="utf-8")
    mark_pubspec_resolved(tmp_path)
    with patch("figma_flutter_agent.generator.codegen.run_subprocess") as run:
        run_pub_get(tmp_path)
    run.assert_not_called()


def test_run_pub_get_uses_offline_flag(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    with (
        patch("figma_flutter_agent.generator.codegen.shutil.which", return_value="/flutter"),
        patch("figma_flutter_agent.generator.codegen.run_subprocess") as run,
    ):
        run.return_value.returncode = 0
        run_pub_get(tmp_path, force=True)
    assert run.call_args[0][0] == ["/flutter", "pub", "get", "--offline"]


def test_run_pub_get_raises_on_failure(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    with (
        patch("figma_flutter_agent.generator.codegen.shutil.which", return_value="/flutter"),
        patch("figma_flutter_agent.generator.codegen.run_subprocess") as run,
    ):
        run.return_value.returncode = 1
        run.return_value.stderr = "pub get failed"
        run.return_value.stdout = ""
        with pytest.raises(GenerationError, match="pub get failed"):
            run_pub_get(tmp_path, force=True, offline=False)


def test_pubspec_digest_changes_when_yaml_edited(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("name: a\n", encoding="utf-8")
    before = pubspec_digest(tmp_path)
    pubspec.write_text("name: b\n", encoding="utf-8")
    after = pubspec_digest(tmp_path)
    assert before != after
    assert read_pubspec_resolve_stamp(tmp_path) is None
