"""Dart/Flutter executable resolution and pub get."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.tools.process_run import FLUTTER_PUB_GET_TIMEOUT_SEC

_WINDOWS_ZONE_IDENTIFIER_NOISE = re.compile(
    r"^Unblock-File:.*Zone\.Identifier['\"]?\.\s*$",
    re.MULTILINE,
)
_PACKAGE_IMPORT = re.compile(r"""import\s+['"]package:([^/'"]+)/""")
_SKIP_IMPORT_PACKAGES = frozenset({"flutter", "flutter_test", "flutter_svg"})


def _dart_format_target_detail(target: str) -> str:
    """Path label for logs; include file size when the target exists on disk."""
    rel = target.replace("\\", "/")
    path = Path(target)
    if path.is_file():
        return f"{rel} ({path.stat().st_size:,} bytes)"
    return rel


def _toolchain_executables(
    flutter_sdk: str | Path | None = None,
) -> tuple[str | None, str | None]:
    """Resolve ``dart`` and ``flutter`` from PATH or ``FIGMA_FLUTTER_SDK``."""
    from figma_flutter_agent.dev.flutter_sdk import (
        resolve_dart_executable,
        resolve_flutter_executable,
    )

    dart = resolve_dart_executable(sdk_root=flutter_sdk)
    flutter = resolve_flutter_executable(sdk_root=flutter_sdk)
    return dart, flutter


def _resolve_dart_executable(flutter_sdk: str | Path | None = None) -> str | None:
    """Return a Dart CLI path (PATH or ``FIGMA_FLUTTER_SDK``)."""
    dart, _ = _toolchain_executables(flutter_sdk)
    return dart


def _strip_windows_zone_identifier_noise(text: str | None) -> str:
    """Remove Flutter SDK ``Unblock-File`` noise from captured CLI stderr."""
    if not text:
        return ""
    cleaned = _WINDOWS_ZONE_IDENTIFIER_NOISE.sub("", text)
    return cleaned.strip()


def _run_flutter_pub_get(
    project_dir: Path,
    flutter: str | None,
    *,
    pubspec_changed: bool | None = None,
    force: bool = False,
) -> "ProjectAnalyzeResult | None":
    """Resolve packages in a Flutter project before analyze. Returns failure or None."""
    from figma_flutter_agent.generator.codegen import run_pub_get
    from .analyze import ProjectAnalyzeResult, _timeout_analyze_result  # noqa: PLC0415

    if flutter is None:
        return None
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.is_file():
        return None
    try:
        run_pub_get(
            project_dir,
            pubspec_changed=pubspec_changed,
            force=force,
        )
    except GenerationError as exc:
        detail = str(exc)
        if "timed out" in detail:
            return _timeout_analyze_result("flutter pub get", FLUTTER_PUB_GET_TIMEOUT_SEC)
        return ProjectAnalyzeResult(
            passed=False,
            detail="flutter pub get failed before analyze",
            analyze_output=detail,
        )
    return None


def _read_package_name(project_dir: Path) -> str:
    """Read the package name from ``pubspec.yaml``."""
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.is_file():
        return "demo_app"
    for line in pubspec.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip()
    return "demo_app"


def align_skeleton_pubspec_package_name(project_dir: Path, package_name: str) -> None:
    """Rewrite the temp skeleton ``pubspec.yaml`` name to match the target Flutter app.

    The analyze/parse-gate harness copies ``tests/fixtures/flutter_skeleton`` (default
    ``name: demo_app``). Planned Dart for ``demo_app2`` and other apps must keep their
    ``package:<app>/`` imports while ``dart format`` / ``dart analyze`` run in the temp tree.

    Args:
        project_dir: Temporary Flutter project root (skeleton copy).
        package_name: Package name from the real project's ``pubspec.yaml``.
    """
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.is_file():
        return
    lines = pubspec.read_text(encoding="utf-8").splitlines(keepends=True)
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.strip().startswith("name:"):
            updated.append(f"name: {package_name}\n")
            replaced = True
        else:
            updated.append(line if line.endswith("\n") else f"{line}\n")
    if not replaced:
        updated.insert(0, f"name: {package_name}\n")
    pubspec.write_text("".join(updated), encoding="utf-8")


def _validate_package_imports(planned: dict[str, str], package_name: str) -> str | None:
    """Return an error message when planned Dart uses the wrong package import prefix."""
    expected = f"package:{package_name}/"
    for path, content in planned.items():
        if not path.endswith(".dart"):
            continue
        for match in _PACKAGE_IMPORT.finditer(content):
            imported = match.group(1)
            if imported in _SKIP_IMPORT_PACKAGES:
                continue
            prefix = f"package:{imported}/"
            if prefix != expected:
                return (
                    f"{path} imports {prefix!r} but skeleton package is {package_name!r} "
                    f"(expected {expected!r})"
                )
    return None
