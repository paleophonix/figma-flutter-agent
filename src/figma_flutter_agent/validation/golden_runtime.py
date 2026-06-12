"""Select host vs Docker runtime for Flutter golden capture."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from loguru import logger

from figma_flutter_agent.config import Settings, agent_repo_root

GoldenCaptureMode = Literal["auto", "docker", "host"]
ResolvedGoldenRuntime = Literal["host", "docker"]

_COMPOSE_FILE = agent_repo_root() / "tools" / "render-capture" / "docker-compose.yml"


@dataclass(frozen=True)
class GoldenRuntimeSelection:
    """Resolved runtime for a single golden capture attempt."""

    runtime: ResolvedGoldenRuntime
    configured: GoldenCaptureMode
    fallback_from_docker: bool = False


def _configured_mode(settings: Settings | None) -> GoldenCaptureMode:
    env_raw = os.environ.get("FIGMA_GOLDEN_RUNTIME", "").strip().lower()
    if env_raw in ("auto", "docker", "host"):
        return env_raw  # type: ignore[return-value]
    if settings is not None:
        return settings.agent.runtime.golden_capture
    return "auto"


def docker_cli_available() -> bool:
    """Return True when the Docker CLI responds to ``docker info``."""
    docker = shutil.which("docker")
    if docker is None:
        return False
    try:
        result = subprocess.run(
            [docker, "info"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def golden_compose_file() -> Path:
    """Return the docker-compose path for golden capture."""
    return _COMPOSE_FILE


def resolve_golden_runtime(
    mode: GoldenCaptureMode | None = None,
    *,
    settings: Settings | None = None,
    no_docker: bool = False,
) -> GoldenRuntimeSelection:
    """Resolve ``auto`` / ``docker`` / ``host`` to a concrete capture backend.

    Args:
        mode: Optional override; defaults to YAML/env ``golden_capture``.
        settings: Optional loaded settings.
        no_docker: When True, force host (CLI ``--no-docker``).

    Returns:
        Selection with resolved ``host`` or ``docker`` runtime.
    """
    configured = mode or _configured_mode(settings)
    if no_docker:
        return GoldenRuntimeSelection(runtime="host", configured=configured)

    if configured == "host":
        return GoldenRuntimeSelection(runtime="host", configured=configured)

    if configured == "docker":
        if docker_cli_available() and _COMPOSE_FILE.is_file():
            return GoldenRuntimeSelection(runtime="docker", configured=configured)
        return GoldenRuntimeSelection(
            runtime="host",
            configured=configured,
            fallback_from_docker=True,
        )

    if docker_cli_available() and _COMPOSE_FILE.is_file():
        return GoldenRuntimeSelection(runtime="docker", configured=configured)

    logger.warning(
        "Docker golden runtime unavailable (missing CLI or compose file); using host capture"
    )
    return GoldenRuntimeSelection(
        runtime="host",
        configured="auto",
        fallback_from_docker=True,
    )
