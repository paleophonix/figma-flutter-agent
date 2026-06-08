"""AST sidecar compiler discovery."""

from __future__ import annotations

import functools
import os
import sys
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import agent_repo_root
from figma_flutter_agent.dev.flutter_sdk import resolve_dart_executable
from figma_flutter_agent.tools.ast_sidecar.types import AST_REQUIRED_MSG, AstSidecarError


def sidecar_root() -> Path:
    return agent_repo_root() / "tools" / "dart_ast_sidecar"


def prebuilt_compiler_basename() -> str:
    if sys.platform == "win32":
        return "ast_compiler.exe"
    if sys.platform == "darwin":
        return "ast_compiler-macos"
    return "ast_compiler-linux"


def prebuilt_compiler_path() -> Path | None:
    bin_dir = agent_repo_root() / "tools" / "bin"
    candidate = bin_dir / prebuilt_compiler_basename()
    return candidate if candidate.is_file() else None


def compiler_invocation_dart_run() -> list[str] | None:
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
    if dart is None:
        from figma_flutter_agent.dev.flutter_sdk import flutter_sdk_root_from_agent_dotenv

        dotenv_sdk = flutter_sdk_root_from_agent_dotenv()
        if dotenv_sdk:
            dart = resolve_dart_executable(sdk_root=dotenv_sdk)
    root = sidecar_root()
    entry = root / "bin" / "ast_compiler.dart"
    if dart is None or not entry.is_file():
        return None
    return [dart, "run", "bin/ast_compiler.dart"]


def sidecar_sources_newer_than_prebuilt(prebuilt: Path) -> bool:
    """True when Dart sidecar sources changed after the packaged AOT binary was built."""
    marker = sidecar_root() / "lib" / "rules_syntax_repairs.dart"
    if not marker.is_file():
        return False
    try:
        return marker.stat().st_mtime > prebuilt.stat().st_mtime
    except OSError:
        return False


_stale_prebuilt_warned = False


def compiler_invocation() -> list[str] | None:
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
    prebuilt = prebuilt_compiler_path()
    dart_run = compiler_invocation_dart_run()
    if prebuilt is not None:
        if prefer_dart_run and dart_run is not None:
            return dart_run
        if sidecar_sources_newer_than_prebuilt(prebuilt):
            global _stale_prebuilt_warned
            if not _stale_prebuilt_warned:
                logger.warning(
                    "AST sidecar sources are newer than {} - using prebuilt (fast). "
                    "Run tools/build_sidecars.ps1 when figma-flutter is stopped, "
                    "or set FIGMA_AST_COMPILER_PREFER_DART_RUN=1 to use dart run.",
                    prebuilt.name,
                )
                _stale_prebuilt_warned = True
        return [str(prebuilt)]

    return dart_run


@functools.lru_cache(maxsize=1)
def cached_compiler_command() -> tuple[str, ...]:
    command = compiler_invocation()
    if command is None:
        raise AstSidecarError(AST_REQUIRED_MSG)
    return tuple(command)


def reset_ast_compiler_command_cache() -> None:
    """Clear cached compiler path (e.g. after a crashed or killed sidecar process)."""
    cached_compiler_command.cache_clear()


def require_ast_compiler() -> list[str]:
    """Return a sidecar command vector or raise."""
    return list(cached_compiler_command())
