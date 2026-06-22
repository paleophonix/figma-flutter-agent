"""Tests for OpenCode serve process helpers."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.dev.opencode.serve_process import (
    pids_listening_on_port,
    stop_listeners_on_port,
)


def test_pids_listening_on_port_windows_parses_netstat() -> None:
    stdout = (
        "  TCP    127.0.0.1:4096         0.0.0.0:0              LISTENING       40020\n"
        "  TCP    127.0.0.1:4096         127.0.0.1:60814        ESTABLISHED     40020\n"
    )
    with patch("sys.platform", "win32"), patch(
        "figma_flutter_agent.dev.opencode.serve_process.subprocess.run",
        return_value=type("R", (), {"stdout": stdout, "returncode": 0})(),
    ):
        assert pids_listening_on_port(4096) == [40020]


def test_stop_listeners_on_port_kills_listeners() -> None:
    with patch(
        "figma_flutter_agent.dev.opencode.serve_process.pids_listening_on_port",
        return_value=[111, 222],
    ), patch(
        "figma_flutter_agent.dev.opencode.serve_process._terminate_pid",
        side_effect=lambda pid: True,
    ) as terminate:
        stopped = stop_listeners_on_port(4096, exclude_pids=[222])
    assert stopped == [111]
    terminate.assert_called_once_with(111)
