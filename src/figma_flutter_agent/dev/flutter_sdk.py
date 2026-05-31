"""Resolve Flutter and Dart SDK executables from env or PATH."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_SDK_ENV_NAMES = ("FIGMA_FLUTTER_SDK", "FLUTTER_ROOT")
_PATH_REFRESHED = False


def _refresh_windows_path() -> None:
    """Merge user and machine PATH entries on Windows (helps VS Code tasks)."""
    global _PATH_REFRESHED
    if _PATH_REFRESHED or sys.platform != "win32":
        return
    _PATH_REFRESHED = True
    try:
        import winreg
    except ImportError:
        return

    parts: list[str] = []
    for hive, key_name in (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ):
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
                if value:
                    parts.append(str(value))
        except OSError:
            continue
    if parts:
        os.environ["PATH"] = os.pathsep.join(parts + [os.environ.get("PATH", "")])


def _flutter_from_sdk_root(root: Path) -> Path | None:
    bin_dir = root.expanduser().resolve() / "bin"
    candidate = bin_dir / ("flutter.bat" if sys.platform == "win32" else "flutter")
    return candidate if candidate.is_file() else None


def flutter_sdk_root_from_agent_dotenv() -> str | None:
    """Read ``FIGMA_FLUTTER_SDK`` from the agent repo ``.env`` (when not loaded via Settings)."""
    from figma_flutter_agent.config import agent_repo_root

    env_path = agent_repo_root() / ".env"
    if not env_path.is_file():
        return None
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "FIGMA_FLUTTER_SDK":
            continue
        cleaned = value.strip().strip('"').strip("'")
        return cleaned or None
    return None


def _sdk_roots_from_env(*, sdk_root: str | Path | None = None) -> list[Path]:
    roots: list[Path] = []
    if sdk_root is not None and str(sdk_root).strip():
        roots.append(Path(str(sdk_root).strip()))
    for name in _SDK_ENV_NAMES:
        raw = os.environ.get(name, "").strip()
        if raw:
            roots.append(Path(raw))
    return roots


def resolve_flutter_executable(*, sdk_root: str | Path | None = None) -> str | None:
    """Return the ``flutter`` executable path when available.

    Precedence:
        1. Explicit ``sdk_root`` or ``FIGMA_FLUTTER_SDK`` / ``FLUTTER_ROOT`` env
        2. ``flutter`` on PATH (after Windows PATH refresh when needed)

    Args:
        sdk_root: Optional SDK root directory override.

    Returns:
        Absolute path to the Flutter executable, or ``None``.
    """
    for root in _sdk_roots_from_env(sdk_root=sdk_root):
        candidate = _flutter_from_sdk_root(root)
        if candidate is not None:
            return str(candidate)

    _refresh_windows_path()
    return shutil.which("flutter")


def resolve_dart_executable(*, sdk_root: str | Path | None = None) -> str | None:
    """Return the ``dart`` executable path when available."""
    flutter = resolve_flutter_executable(sdk_root=sdk_root)
    if flutter is not None:
        sdk_bin = Path(flutter).parent
        dart_name = "dart.bat" if sys.platform == "win32" else "dart"
        dart = sdk_bin / dart_name
        if dart.is_file():
            return str(dart)

    _refresh_windows_path()
    return shutil.which("dart")


def require_flutter_executable(*, sdk_root: str | Path | None = None) -> str:
    """Return the Flutter executable or raise with setup guidance.

    Args:
        sdk_root: Optional SDK root directory override.

    Returns:
        Absolute path to the Flutter executable.

    Raises:
        RuntimeError: When Flutter cannot be resolved.
    """
    flutter = resolve_flutter_executable(sdk_root=sdk_root)
    if flutter is None:
        msg = (
            "Flutter SDK not found. Add Flutter to PATH or set "
            "FIGMA_FLUTTER_SDK (or FLUTTER_ROOT) in .env to the SDK root directory."
        )
        raise RuntimeError(msg)
    return flutter
