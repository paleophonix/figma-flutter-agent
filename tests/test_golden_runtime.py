"""Tests for golden capture runtime selection."""

from __future__ import annotations

from figma_flutter_agent.config import RuntimeConfig, Settings
from figma_flutter_agent.validation.golden_runtime import resolve_golden_runtime


def test_resolve_golden_runtime_force_host_with_no_docker() -> None:
    selection = resolve_golden_runtime("docker", no_docker=True)
    assert selection.runtime == "host"
    assert selection.configured == "docker"


def test_resolve_golden_runtime_host_mode() -> None:
    selection = resolve_golden_runtime("host")
    assert selection.runtime == "host"


def test_resolve_golden_runtime_reads_yaml() -> None:
    settings = Settings(
        agent={
            "runtime": RuntimeConfig(golden_capture="host"),
        }
    )
    selection = resolve_golden_runtime(settings=settings)
    assert selection.runtime == "host"
    assert selection.configured == "host"
