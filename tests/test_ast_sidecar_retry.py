"""AST sidecar transient failure retry."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from figma_flutter_agent.tools.ast_sidecar import (
    AST_SIDECAR_MAX_SOURCE_BYTES,
    AstSidecarError,
    apply_codegen_ast_rules,
)
from figma_flutter_agent.tools.ast_sidecar.commands import reset_ast_compiler_command_cache
from figma_flutter_agent.tools.ast_sidecar.transport import (
    invoke_sidecar_json,
    sidecar_failure_is_transient,
)

def test_transient_failure_detects_empty_stderr_exit_one() -> None:
    proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    assert sidecar_failure_is_transient(proc) is True


def test_transient_failure_false_when_stderr_present() -> None:
    proc = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr="parse error at line 3",
    )
    assert sidecar_failure_is_transient(proc) is False


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
        "figma_flutter_agent.tools.ast_sidecar.transport.subprocess.run",
        side_effect=[fail, ok],
    ) as run_mock:
        result = invoke_sidecar_json(
            ["ast_compiler.exe"],
            {"version": 1, "command": "apply_rules", "source": "class A {}"},
        )
    assert result["ok"] is True
    assert run_mock.call_count == 2


def test_invoke_sidecar_raises_on_oversized_source_without_subprocess() -> None:
    reset_ast_compiler_command_cache()
    huge = "x" * (AST_SIDECAR_MAX_SOURCE_BYTES + 1)
    with patch("figma_flutter_agent.tools.ast_sidecar.transport.subprocess.run") as run_mock:
        with pytest.raises(AstSidecarError, match="exceeds"):
            invoke_sidecar_json(
                ["ast_compiler.exe"],
                {"version": 1, "command": "apply_rules", "source": huge},
            )
    run_mock.assert_not_called()


def test_invoke_sidecar_allows_extract_widget_on_oversized_source() -> None:
    reset_ast_compiler_command_cache()
    huge = "x" * (AST_SIDECAR_MAX_SOURCE_BYTES + 1)
    ok = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"ok": true, "snippet": "Text()"}',
        stderr="",
    )
    with patch(
        "figma_flutter_agent.tools.ast_sidecar.transport.subprocess.run",
        return_value=ok,
    ) as run_mock:
        result = invoke_sidecar_json(
            ["ast_compiler.exe"],
            {
                "version": 1,
                "command": "extract_widget",
                "source": huge,
                "figmaId": "1:2",
            },
        )
    assert result["ok"] is True
    run_mock.assert_called_once()


def test_apply_codegen_ast_rules_oversized_skips_codegen_pass() -> None:
    reset_ast_compiler_command_cache()
    padding = "x" * (AST_SIDECAR_MAX_SOURCE_BYTES + 1)
    source = f"{padding}\nkey: ValueKey('figma-1_2'),\n"
    with (
        patch(
            "figma_flutter_agent.tools.ast_sidecar.require_ast_compiler",
            return_value=["ast_compiler.exe"],
        ),
        patch(
            "figma_flutter_agent.tools.ast_sidecar.apply_rules_chunked_by_figma_keys",
        ) as chunked_mock,
        patch("figma_flutter_agent.tools.ast_sidecar.apply_rules_subprocess") as full_mock,
    ):
        result = apply_codegen_ast_rules(source)
    chunked_mock.assert_not_called()
    full_mock.assert_not_called()
    assert result.source == source
    assert result.backend == "skipped"


def test_invoke_sidecar_raises_after_two_transient_failures() -> None:
    reset_ast_compiler_command_cache()
    fail = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    with patch(
        "figma_flutter_agent.tools.ast_sidecar.transport.subprocess.run",
        return_value=fail,
    ), pytest.raises(AstSidecarError, match="no stderr"):
        invoke_sidecar_json(
            ["ast_compiler.exe"],
            {"version": 1, "command": "apply_rules", "source": "class A {}"},
        )
