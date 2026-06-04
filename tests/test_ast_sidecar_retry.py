"""AST sidecar transient failure retry."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from figma_flutter_agent.tools.ast_sidecar import (
    AST_SIDECAR_MAX_SOURCE_BYTES,
    AstSidecarError,
    _invoke_sidecar_json,
    _sidecar_failure_is_transient,
    reset_ast_compiler_command_cache,
)


def test_transient_failure_detects_empty_stderr_exit_one() -> None:
    proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    assert _sidecar_failure_is_transient(proc) is True


def test_transient_failure_false_when_stderr_present() -> None:
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr="parse error at line 3",
    )
    assert _sidecar_failure_is_transient(proc) is False


def test_invoke_sidecar_retries_once_on_transient_crash() -> None:
    reset_ast_compiler_command_cache()
    ok = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"ok": true, "source": "class A {}"}',
        stderr="",
    )
    fail = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    with patch(
        "figma_flutter_agent.tools.ast_sidecar.subprocess.run",
        side_effect=[fail, ok],
    ) as run_mock:
        result = _invoke_sidecar_json(
            ["ast_compiler.exe"],
            {"version": 1, "command": "apply_rules", "source": "class A {}"},
        )
    assert result["ok"] is True
    assert run_mock.call_count == 2


def test_invoke_sidecar_skips_oversized_source_without_subprocess() -> None:
    reset_ast_compiler_command_cache()
    huge = "x" * (AST_SIDECAR_MAX_SOURCE_BYTES + 1)
    with patch("figma_flutter_agent.tools.ast_sidecar.subprocess.run") as run_mock:
        result = _invoke_sidecar_json(
            ["ast_compiler.exe"],
            {"version": 1, "command": "apply_rules", "source": huge},
        )
    run_mock.assert_not_called()
    assert result.get("skipped") == "oversized"
    assert result["source"] == huge


def test_invoke_sidecar_raises_after_two_transient_failures() -> None:
    reset_ast_compiler_command_cache()
    fail = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    with patch(
        "figma_flutter_agent.tools.ast_sidecar.subprocess.run",
        return_value=fail,
    ):
        with pytest.raises(AstSidecarError, match="no stderr"):
            _invoke_sidecar_json(
                ["ast_compiler.exe"],
                {"version": 1, "command": "apply_rules", "source": "class A {}"},
            )
