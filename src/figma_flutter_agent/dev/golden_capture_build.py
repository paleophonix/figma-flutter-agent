"""Build and preflight checks for the Docker golden-capture image."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import Settings, agent_repo_root
from figma_flutter_agent.validation.golden_runtime import (
    docker_cli_available,
    golden_compose_file,
)

GOLDEN_CAPTURE_IMAGE = "figma-flutter-golden-capture:local"


@dataclass(frozen=True)
class GoldenCapturePreflight:
    """Docker is available but the golden-capture image is not built yet."""

    compose_file: Path
    image_name: str
    build_hint: Path


def _golden_build_hint_path() -> Path:
    root = agent_repo_root()
    ps1 = root / "scripts" / "update-golden-docker.ps1"
    if os.name == "nt" and ps1.is_file():
        return ps1
    return root / "docker" / "render-capture" / "docker-compose.yml"


def golden_capture_image_present(image: str = GOLDEN_CAPTURE_IMAGE) -> bool:
    """Return True when ``docker image inspect`` succeeds for the golden image."""
    if not docker_cli_available():
        return False
    docker = os.environ.get("DOCKER", "docker")
    result = subprocess.run(
        [docker, "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return result.returncode == 0


def golden_docker_auto_build_enabled() -> bool:
    """Return False when ``FIGMA_GOLDEN_CAPTURE_AUTO_BUILD=0`` (opt-out for CI)."""
    return os.environ.get("FIGMA_GOLDEN_CAPTURE_AUTO_BUILD", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _skip_golden_build_prompt() -> bool:
    return os.environ.get("FIGMA_GOLDEN_CAPTURE_SKIP_BUILD_PROMPT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def golden_capture_preflight(settings: Settings | None = None) -> GoldenCapturePreflight | None:
    """Return preflight info when Docker is on but the golden image is missing.

    Args:
        settings: When set, skipped when resolved runtime is not ``docker``.

    Returns:
        ``None`` when Docker is off, compose is missing, or the image already exists.
    """
    if settings is not None:
        from figma_flutter_agent.validation.golden_runtime import resolve_golden_runtime

        if resolve_golden_runtime(settings=settings).runtime != "docker":
            return None
    if not docker_cli_available():
        return None
    compose = golden_compose_file()
    if not compose.is_file():
        return None
    if golden_capture_image_present():
        return None
    return GoldenCapturePreflight(
        compose_file=compose,
        image_name=GOLDEN_CAPTURE_IMAGE,
        build_hint=_golden_build_hint_path(),
    )


def build_golden_capture_image(*, flutter_version: str | None = None) -> str:
    """Build the ``golden-capture`` Docker image via compose.

    Args:
        flutter_version: Optional Flutter SDK version passed as build-arg.

    Returns:
        The image tag (``figma-flutter-golden-capture:local``).

    Raises:
        RuntimeError: When Docker or compose is unavailable, or the build fails.
    """
    if not docker_cli_available():
        msg = "Docker is not available. Install Docker or use runtime.golden_capture: host"
        raise RuntimeError(msg)
    compose = golden_compose_file()
    if not compose.is_file():
        msg = f"Missing golden compose file: {compose}"
        raise RuntimeError(msg)

    docker = os.environ.get("DOCKER", "docker")
    env = os.environ.copy()
    if flutter_version and flutter_version.strip():
        env["FLUTTER_VERSION"] = flutter_version.strip()
    elif (agent_repo_root() / ".flutter-version").is_file():
        env["FLUTTER_VERSION"] = (
            (agent_repo_root() / ".flutter-version").read_text(encoding="utf-8").strip()
        )

    command = [
        docker,
        "compose",
        "-f",
        str(compose),
        "build",
        "golden-capture",
    ]
    logger.info("Building golden-capture image ({})", GOLDEN_CAPTURE_IMAGE)
    completed = subprocess.run(
        command,
        cwd=agent_repo_root(),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        msg = f"golden-capture build failed (exit {completed.returncode}): {detail}"
        raise RuntimeError(msg)
    if not golden_capture_image_present():
        msg = f"Build finished but image missing: {GOLDEN_CAPTURE_IMAGE}"
        raise RuntimeError(msg)
    return GOLDEN_CAPTURE_IMAGE


def ensure_golden_capture_image(
    settings: Settings | None = None,
    *,
    interactive: bool = False,
    build_if_missing: bool = False,
    print_hint: bool = True,
    console_print: Callable[[str], None] | None = None,
) -> bool:
    """Warn or build when the golden-capture Docker image is missing.

    Args:
        settings: Optional loaded settings.
        interactive: When True, prompt to build (TTY sessions).
        build_if_missing: Build without prompting (e.g. ``doctor --build-golden``).
        print_hint: Emit user-facing hints when not building.
        console_print: Optional sink for messages.

    Returns:
        True when the image exists, Docker is off, or build succeeded.
    """
    preflight = golden_capture_preflight(settings)
    if preflight is None:
        return True

    def emit(message: str) -> None:
        if console_print is not None:
            console_print(message)
        else:
            logger.info(message)

    script_ref = preflight.build_hint.relative_to(agent_repo_root())
    emit(f"Golden capture image missing ({preflight.image_name}); build: {script_ref}")

    should_build = build_if_missing or (
        golden_docker_auto_build_enabled() and not interactive
    )
    if not should_build and interactive and not _skip_golden_build_prompt():
        import typer

        should_build = typer.confirm(
            f"Build Docker image {preflight.image_name} now?",
            default=True,
        )

    if should_build:
        try:
            built = build_golden_capture_image()
        except RuntimeError as exc:
            emit(f"Golden capture build failed: {exc}")
            return False
        emit(f"Built golden-capture image: {built}")
        return True

    if print_hint:
        emit(f"To build now: {script_ref}")
    return False
