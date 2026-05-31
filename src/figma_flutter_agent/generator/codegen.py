"""Run Flutter/Dart codegen helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.pub_get_policy import (
    log_pub_get_skip,
    mark_pubspec_resolved,
    needs_pub_get,
)
from figma_flutter_agent.tools.process_run import (
    BUILD_RUNNER_TIMEOUT_SEC,
    FLUTTER_PUB_GET_TIMEOUT_SEC,
    run_subprocess,
)


def _pub_get_argv(
    flutter: str | None,
    dart: str | None,
    *,
    offline: bool,
) -> list[str] | None:
    if flutter is not None:
        command: list[str] = [flutter, "pub", "get"]
    elif dart is not None:
        command = [dart, "pub", "get"]
    else:
        return None
    if offline:
        command.append("--offline")
    return command


def run_pub_get(
    project_dir: Path,
    *,
    require_dart_sdk: bool = False,
    offline: bool = True,
    pubspec_changed: bool | None = None,
    force: bool = False,
) -> None:
    """Resolve package dependencies for a Flutter project when needed.

    Skips network work when ``pubspec.yaml`` is unchanged since the last successful
    resolve (see ``pub_get_policy``). Uses ``--offline`` by default for fast cache-only
    resolves; retries online when offline fails after a pubspec edit.
    """
    if not needs_pub_get(project_dir, pubspec_changed=pubspec_changed, force=force):
        log_pub_get_skip(project_dir)
        return

    flutter = shutil.which("flutter")
    dart = shutil.which("dart")
    command = _pub_get_argv(flutter, dart, offline=offline)
    if command is None:
        if require_dart_sdk:
            raise GenerationError(
                "Neither flutter nor dart executable found; required for pub get (auto_route)"
            )
        logger.warning("Neither flutter nor dart found; skipping pub get")
        return

    label = "pub get --offline" if offline else "pub get"
    try:
        result = run_subprocess(
            command,
            cwd=project_dir,
            label=label,
            timeout_sec=FLUTTER_PUB_GET_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        raise GenerationError(
            f"pub get timed out after {FLUTTER_PUB_GET_TIMEOUT_SEC:.0f}s"
        ) from exc

    if result.returncode != 0 and offline:
        logger.warning("pub get --offline failed; retrying with network")
        online = _pub_get_argv(flutter, dart, offline=False)
        if online is not None:
            try:
                result = run_subprocess(
                    online,
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

    mark_pubspec_resolved(project_dir)


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
