"""AST sidecar client: subprocess compiler (required for codegen)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from figma_flutter_agent.config import agent_repo_root
from figma_flutter_agent.dev.flutter_sdk import resolve_dart_executable
from figma_flutter_agent.errors import FigmaFlutterError

AstRule = Literal[
    "codegen_pass",
    "strip_bare_unicode_escapes",
    "normalize_string_literals",
    "sanitize_imports",
    "unscale_design_expressions",
    "unwrap_scale_layout_builder",
    "strip_viewport_scale_transform",
    "fix_llm_api_mistakes",
    "fix_alignment_literals",
    "strip_design_canvas_gesture_matryoshka",
    "wrap_flex_row_column_children",
    "llm_syntax_repairs",
    "planned_delimiter_balance",
]

_LAYOUT_RULES: tuple[AstRule, ...] = (
    "unscale_design_expressions",
    "unwrap_scale_layout_builder",
    "strip_viewport_scale_transform",
)

CODEGEN_AST_RULES: tuple[AstRule, ...] = ("codegen_pass",)

_AST_REQUIRED_MSG = (
    "Dart AST sidecar is required. Set FIGMA_FLUTTER_SDK (or PATH to dart), "
    "run tools/build_sidecars.ps1, or set FIGMA_AST_COMPILER_PATH to a built ast_compiler binary."
)


class AstSidecarError(FigmaFlutterError):
    """Raised when the AST sidecar cannot apply rules."""


@dataclass(frozen=True)
class AstSidecarResult:
    """Outcome of an AST sidecar invocation."""

    source: str
    backend: Literal["subprocess"]
    edits: list[dict[str, Any]]


def _sidecar_root() -> Path:
    return agent_repo_root() / "tools" / "dart_ast_sidecar"


def _prebuilt_compiler_basename() -> str:
    if sys.platform == "win32":
        return "ast_compiler.exe"
    if sys.platform == "darwin":
        return "ast_compiler-macos"
    return "ast_compiler-linux"


def _prebuilt_compiler_path() -> Path | None:
    bin_dir = agent_repo_root() / "tools" / "bin"
    candidate = bin_dir / _prebuilt_compiler_basename()
    return candidate if candidate.is_file() else None


def _compiler_invocation_dart_run() -> list[str] | None:
    dart = resolve_dart_executable()
    if dart is None:
        try:
            from figma_flutter_agent.config import load_settings

            dart = resolve_dart_executable(sdk_root=load_settings().flutter_sdk)
        except Exception:
            dart = None
    if dart is None:
        for name in ("FIGMA_FLUTTER_SDK", "FLUTTER_ROOT"):
            raw = os.environ.get(name, "").strip()
            if raw:
                dart = resolve_dart_executable(sdk_root=raw)
                if dart is not None:
                    break
    root = _sidecar_root()
    entry = root / "bin" / "ast_compiler.dart"
    if dart is None or not entry.is_file():
        return None
    return [dart, "run", "bin/ast_compiler.dart"]


def _sidecar_sources_newer_than_prebuilt(prebuilt: Path) -> bool:
    """True when Dart sidecar sources changed after the packaged AOT binary was built."""
    root = _sidecar_root()
    marker = root / "lib" / "rules_syntax_repairs.dart"
    if not marker.is_file():
        return False
    try:
        return marker.stat().st_mtime > prebuilt.stat().st_mtime
    except OSError:
        return False


def _compiler_invocation() -> list[str] | None:
    override = os.environ.get("FIGMA_AST_COMPILER_PATH", "").strip()
    if override:
        path = Path(override)
        if path.is_file():
            return [str(path)]
        raise AstSidecarError(f"FIGMA_AST_COMPILER_PATH not found: {path}")

    prefer_dart_run = os.environ.get("FIGMA_AST_COMPILER_PREFER_DART_RUN", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    prebuilt = _prebuilt_compiler_path()
    dart_run = _compiler_invocation_dart_run()
    if prebuilt is not None:
        sources_newer = _sidecar_sources_newer_than_prebuilt(prebuilt)
        if prefer_dart_run or sources_newer:
            if dart_run is not None:
                return dart_run
            if sources_newer:
                raise AstSidecarError(
                    "Dart AST sidecar sources are newer than tools/bin/ast_compiler.exe. "
                    "Set FIGMA_FLUTTER_SDK (or run tools/build_sidecars.ps1 after stopping "
                    "figma-flutter) so planned_delimiter_balance can run via dart run."
                )
        return [str(prebuilt)]

    return dart_run


def require_ast_compiler() -> list[str]:
    """Return a sidecar command vector or raise."""
    command = _compiler_invocation()
    if command is None:
        raise AstSidecarError(_AST_REQUIRED_MSG)
    return command


def _invoke_sidecar_json(
    command: list[str],
    payload: dict[str, Any],
    *,
    timeout: int = 120,
    require_ok: bool = True,
) -> dict[str, Any]:
    if len(str(payload.get("source", ""))) > 8_000_000:
        raise AstSidecarError("Dart source exceeds AST sidecar size limit (8MB)")
    run_cwd: Path | None = None
    if len(command) >= 3 and command[-1] == "bin/ast_compiler.dart":
        run_cwd = _sidecar_root()
    proc = subprocess.run(
        command,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
        cwd=str(run_cwd) if run_cwd is not None else None,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise AstSidecarError(f"AST sidecar exited {proc.returncode}: {stderr[:500]}")
    try:
        response: dict[str, Any] = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise AstSidecarError("AST sidecar returned invalid JSON") from exc
    if require_ok and not response.get("ok"):
        errors = response.get("errors") or []
        raise AstSidecarError(f"AST sidecar failed: {errors}")
    return response


def _apply_rules_subprocess(
    source: str,
    rules: tuple[AstRule, ...],
    *,
    include_text_scaler: bool,
    command: list[str],
) -> AstSidecarResult:
    response = _invoke_sidecar_json(
        command,
        {
            "version": 1,
            "command": "apply_rules",
            "source": source,
            "rules": list(rules),
            "options": {"includeTextScaler": include_text_scaler},
        },
    )
    return AstSidecarResult(
        source=str(response.get("source", source)),
        backend="subprocess",
        edits=list(response.get("edits") or []),
    )


def apply_ast_rules(
    source: str,
    rules: tuple[AstRule, ...] | None = None,
    *,
    include_text_scaler: bool = True,
    prefer_subprocess: bool = True,
) -> AstSidecarResult:
    """Apply Dart AST sidecar rules to generated source."""
    del prefer_subprocess
    command = require_ast_compiler()
    return _apply_rules_subprocess(
        source,
        rules or _LAYOUT_RULES,
        include_text_scaler=include_text_scaler,
        command=command,
    )


def apply_codegen_ast_rules(
    source: str,
    *,
    include_text_scaler: bool = True,
    prefer_subprocess: bool = True,
) -> AstSidecarResult:
    """Run the full codegen AST pass."""
    del prefer_subprocess
    command = require_ast_compiler()
    return _apply_rules_subprocess(
        source,
        CODEGEN_AST_RULES,
        include_text_scaler=include_text_scaler,
        command=command,
    )


def ensure_named_widgets_on_pressed(
    source: str,
    widget_names: tuple[str, ...],
) -> str:
    """Inject no-op ``onPressed`` for custom widget constructors."""
    command = require_ast_compiler()
    response = _invoke_sidecar_json(
        command,
        {
            "version": 1,
            "command": "ensure_named_widgets_on_pressed",
            "source": source,
            "widgetNames": list(widget_names),
        },
    )
    return str(response.get("source", source))


def wrap_widget_on_pressed(source: str, widget_name: str) -> str:
    """Move ``onPressed`` from a non-button widget onto ``GestureDetector``."""
    command = require_ast_compiler()
    response = _invoke_sidecar_json(
        command,
        {
            "version": 1,
            "command": "wrap_widget_on_pressed",
            "source": source,
            "widgetName": widget_name,
        },
    )
    return str(response.get("source", source))


def _sidecar_widget_command(
    command: Literal["extract_widget", "replace_widget"],
    source: str,
    figma_id: str,
    *,
    replacement: str | None = None,
) -> dict[str, Any] | None:
    invocation = _compiler_invocation()
    if invocation is None:
        return None
    payload: dict[str, Any] = {
        "version": 1,
        "command": command,
        "source": source,
        "figmaId": figma_id,
    }
    if replacement is not None:
        payload["replacement"] = replacement
    return _invoke_sidecar_json(invocation, payload, require_ok=False)


def extract_widget_by_figma_id(source: str, figma_id: str) -> str | None:
    response = _sidecar_widget_command("extract_widget", source, figma_id)
    if response is None or not response.get("ok"):
        return None
    snippet = response.get("snippet")
    return str(snippet) if snippet is not None else None


def replace_widget_by_figma_id(source: str, figma_id: str, replacement: str) -> str | None:
    response = _sidecar_widget_command("replace_widget", source, figma_id, replacement=replacement)
    if response is None or not response.get("ok"):
        return None
    updated = response.get("source")
    return str(updated) if updated is not None else None
