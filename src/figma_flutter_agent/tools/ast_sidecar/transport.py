"""JSON subprocess transport for the Dart AST sidecar."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.tools.ast_sidecar.commands import (
    reset_ast_compiler_command_cache,
    sidecar_root,
)
from figma_flutter_agent.tools.ast_sidecar.types import (
    AST_SIDECAR_MAX_SOURCE_BYTES,
    SIDECAR_COMMANDS_ALLOWING_OVERSIZED_SOURCE,
    AstSidecarError,
    ast_source_exceeds_sidecar_limit,
)


def oversized_ast_error(source: str) -> AstSidecarError:
    size = len(source.encode("utf-8"))
    return AstSidecarError(
        f"AST sidecar source exceeds {AST_SIDECAR_MAX_SOURCE_BYTES} bytes ({size}); "
        "split layout widgets or enable chunked extraction via smaller subtrees"
    )


def sidecar_failure_is_transient(proc: subprocess.CompletedProcess[str]) -> bool:
    """True when exit looks like an external kill, not a parse error."""
    if proc.returncode == 0:
        return False
    stderr = (proc.stderr or "").strip()
    if stderr:
        return False
    return proc.returncode < 0 or proc.returncode in {1, -9, 137, 143}


def invoke_sidecar_json(
    invocation: list[str],
    payload: dict[str, Any],
    *,
    timeout: int = 120,
    require_ok: bool = True,
) -> dict[str, Any]:
    source_text = str(payload.get("source", ""))
    payload_command = str(payload.get("command", ""))
    if len(source_text) > 8_000_000:
        raise AstSidecarError("Dart source exceeds AST sidecar size limit (8MB)")
    if (
        source_text
        and ast_source_exceeds_sidecar_limit(source_text)
        and payload_command not in SIDECAR_COMMANDS_ALLOWING_OVERSIZED_SOURCE
    ):
        raise oversized_ast_error(source_text)
    run_cwd: Path | None = None
    if len(invocation) >= 3 and invocation[-1] == "bin/ast_compiler.dart":
        run_cwd = sidecar_root()
    proc: subprocess.CompletedProcess[str] | None = None
    for attempt in range(2):
        try:
            proc = subprocess.run(
                invocation,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                cwd=str(run_cwd) if run_cwd is not None else None,
            )
        except subprocess.TimeoutExpired as exc:
            raise AstSidecarError(
                f"AST sidecar timed out after {timeout}s "
                f"(source {len(str(payload.get('source', '')))} chars)"
            ) from exc
        if proc.returncode == 0 or not sidecar_failure_is_transient(proc):
            break
        if attempt == 0:
            logger.warning(
                "AST sidecar exited {} with no stderr; retrying once "
                "(often caused by parallel figma-flutter runs killing ast_compiler)",
                proc.returncode,
            )
            reset_ast_compiler_command_cache()
    assert proc is not None
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        detail = stderr[:500] if stderr else "no stderr (compiler may have crashed)"
        raise AstSidecarError(f"AST sidecar exited {proc.returncode}: {detail}")
    try:
        response: dict[str, Any] = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AstSidecarError("AST sidecar returned invalid JSON") from exc
    if require_ok and not response.get("ok"):
        errors = response.get("errors") or []
        raise AstSidecarError(f"AST sidecar failed: {errors}")
    return response
