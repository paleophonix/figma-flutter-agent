"""Run Flutter/Dart codegen helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.tools.process_run import (
    BUILD_RUNNER_TIMEOUT_SEC,
    FLUTTER_PUB_GET_TIMEOUT_SEC,
    run_subprocess,
)


def run_pub_get(project_dir: Path, *, require_dart_sdk: bool = False) -> None:
    """Resolve package dependencies for a Flutter project.

    Args:
        project_dir: Flutter project root containing ``pubspec.yaml``.
        require_dart_sdk: When True, raise if neither ``flutter`` nor ``dart`` is on ``PATH``.

    Raises:
        GenerationError: If dependency resolution fails or SDK is required but missing.
    """
    flutter = shutil.which("flutter")
    dart = shutil.which("dart")
    if flutter is not None:
        command: list[str] = [flutter, "pub", "get"]
    elif dart is not None:
        command = [dart, "pub", "get"]
    else:
        if require_dart_sdk:
            raise GenerationError(
                "Neither flutter nor dart executable found; required for pub get (auto_route)"
            )
        logger.warning("Neither flutter nor dart found; skipping pub get")
        return

    try:
        result = run_subprocess(
            command,
            cwd=project_dir,
            label="pub get",
            timeout_sec=FLUTTER_PUB_GET_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        raise GenerationError(
            f"pub get timed out after {FLUTTER_PUB_GET_TIMEOUT_SEC:.0f}s"
        ) from exc
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        logger.error("pub get failed: {}", details)
        raise GenerationError("pub get failed for generated project")


def run_build_runner(project_dir: Path, *, require_dart_sdk: bool = False) -> None:
    """Run build_runner for AutoRoute and other codegen.

    Args:
        project_dir: Flutter project root containing ``pubspec.yaml``.
        require_dart_sdk: When True, raise if ``dart`` is not on ``PATH``.

    Raises:
        GenerationError: If build_runner fails or SDK is required but missing.
    """
    dart = shutil.which("dart")
    if dart is None:
        if require_dart_sdk:
            raise GenerationError(
                "dart executable not found; required for build_runner (auto_route)"
            )
        logger.warning("dart executable not found; skipping build_runner")
        return

    try:
        result = run_subprocess(
            [dart, "run", "build_runner", "build", "--delete-conflicting-outputs"],
            cwd=project_dir,
            label="build_runner",
            timeout_sec=BUILD_RUNNER_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        raise GenerationError(
            f"build_runner timed out after {BUILD_RUNNER_TIMEOUT_SEC:.0f}s"
        ) from exc
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        logger.error("build_runner failed: {}", details)
        raise GenerationError("build_runner failed for generated project")

    logger.info("build_runner completed for {}", project_dir)
