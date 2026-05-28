"""Build and preflight checks for the Dart AST sidecar binary."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import Settings, agent_repo_root
from figma_flutter_agent.dev.flutter_sdk import resolve_dart_executable
from figma_flutter_agent.tools.ast_sidecar import (
    _prebuilt_compiler_basename,
    _prebuilt_compiler_path,
)


@dataclass(frozen=True)
class AstSidecarPreflight:
    """AST sidecar is enabled but the native prebuilt binary is absent."""

    expected_binary: Path
    build_script: Path
    can_build: bool
    dart_path: str | None


def _build_script_path() -> Path:
    root = agent_repo_root()
    if sys.platform == "win32":
        return root / "tools" / "build_sidecars.ps1"
    return root / "tools" / "build_sidecars.sh"


def ast_sidecar_preflight(settings: Settings) -> AstSidecarPreflight | None:
    """Return preflight info when AST is on but the OS prebuilt binary is missing.

    Args:
        settings: Loaded agent settings.

    Returns:
        ``None`` when AST is disabled or the prebuilt binary exists.
    """
    if not settings.agent.runtime.use_ast_sidecar:
        return None
    if _prebuilt_compiler_path() is not None:
        return None
    root = agent_repo_root()
    expected = root / "tools" / "bin" / _prebuilt_compiler_basename()
    return AstSidecarPreflight(
        expected_binary=expected,
        build_script=_build_script_path(),
        can_build=resolve_dart_executable(sdk_root=settings.flutter_sdk or None) is not None,
        dart_path=resolve_dart_executable(sdk_root=settings.flutter_sdk or None),
    )


def build_ast_sidecar(*, sdk_root: str | None = None) -> Path:
    """Compile the AST sidecar prebuilt for the current OS.

    Args:
        sdk_root: Optional Flutter SDK root (``FIGMA_FLUTTER_SDK``).

    Returns:
        Path to the compiled binary.

    Raises:
        RuntimeError: When Dart or the build script is unavailable, or compilation fails.
    """
    preflight = AstSidecarPreflight(
        expected_binary=agent_repo_root() / "tools" / "bin" / _prebuilt_compiler_basename(),
        build_script=_build_script_path(),
        can_build=resolve_dart_executable(sdk_root=sdk_root) is not None,
        dart_path=resolve_dart_executable(sdk_root=sdk_root),
    )
    if not preflight.build_script.is_file():
        msg = f"AST build script not found: {preflight.build_script}"
        raise RuntimeError(msg)
    if not preflight.can_build:
        msg = (
            "Dart not found. Set FIGMA_FLUTTER_SDK in .env or add Flutter bin to PATH, "
            f"then run: {preflight.build_script}"
        )
        raise RuntimeError(msg)

    env = os.environ.copy()
    if sdk_root and sdk_root.strip():
        env["FIGMA_FLUTTER_SDK"] = sdk_root.strip()

    root = agent_repo_root()
    if sys.platform == "win32":
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(preflight.build_script),
        ]
    else:
        command = ["bash", str(preflight.build_script)]

    logger.info("Building AST sidecar via {}", preflight.build_script.name)
    completed = subprocess.run(
        command,
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        msg = f"AST sidecar build failed (exit {completed.returncode}): {detail}"
        raise RuntimeError(msg)

    built = _prebuilt_compiler_path()
    if built is None:
        msg = f"Build finished but binary missing: {preflight.expected_binary}"
        raise RuntimeError(msg)
    return built


def _skip_build_prompt() -> bool:
    return os.environ.get("FIGMA_AST_SIDECAR_SKIP_BUILD_PROMPT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def ensure_ast_sidecar_binary(
    settings: Settings,
    *,
    interactive: bool = False,
    build_if_missing: bool = False,
    print_hint: bool = True,
    console_print: Callable[[str], None] | None = None,
) -> bool:
    """Warn or build when the AST prebuilt is missing.

    Args:
        settings: Loaded agent settings.
        interactive: When True, prompt to compile (TTY sessions).
        build_if_missing: Build without prompting (e.g. ``doctor --build-ast``).
        print_hint: Emit user-facing hints when not building.
        console_print: Optional sink for Rich-free messages (one string per call).

    Returns:
        True when the prebuilt binary exists after this call.
    """
    preflight = ast_sidecar_preflight(settings)
    if preflight is None:
        return True

    def emit(message: str) -> None:
        if console_print is not None:
            console_print(message)
        else:
            logger.info(message)

    script_ref = preflight.build_script.relative_to(agent_repo_root())
    emit(
        f"AST sidecar prebuilt missing ({preflight.expected_binary.name}). "
        f"Codegen and postprocess require the binary — build: {script_ref}"
    )

    should_build = build_if_missing
    if not should_build and interactive and not _skip_build_prompt():
        import typer

        should_build = typer.confirm(
            f"Build {preflight.expected_binary.name} now? (requires Dart / Flutter SDK)",
            default=True,
        )

    if should_build:
        if not preflight.can_build:
            emit(
                "Cannot build: Dart not found. Set FIGMA_FLUTTER_SDK in .env "
                f"then run: {script_ref}"
            )
            return False
        try:
            built = build_ast_sidecar(sdk_root=settings.flutter_sdk or None)
        except RuntimeError as exc:
            emit(f"AST sidecar build failed: {exc}")
            return False
        emit(f"Built AST sidecar: {built}")
        return True

    if print_hint and preflight.can_build:
        emit(f"To build now: {script_ref}")
    elif print_hint:
        emit("Set FIGMA_FLUTTER_SDK in .env and run the build script above.")
    return False
