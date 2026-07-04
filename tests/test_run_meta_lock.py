"""run.meta lock behavior tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from figma_flutter_agent.debug.run_meta_lock import run_meta_lifecycle_lock
from figma_flutter_agent.errors import RunMetaStaleWriterError


def test_lock_timeout_does_not_attempt_unlock_when_never_acquired(tmp_path: Path) -> None:
    meta_path = tmp_path / "screen" / "run.meta.json"
    meta_path.parent.mkdir(parents=True)

    fake_msvcrt = MagicMock()
    fake_msvcrt.LK_NBLCK = 8
    fake_msvcrt.LK_UNLCK = 9
    fake_msvcrt.locking.side_effect = OSError(36, "resource deadlock would occur")

    with (
        patch.object(os, "name", "nt"),
        patch("figma_flutter_agent.debug.run_meta_lock.time.monotonic", side_effect=[0.0, 1.0]),
        patch("figma_flutter_agent.debug.run_meta_lock._DEFAULT_LOCK_TIMEOUT_SEC", 0.01),
        patch.dict("sys.modules", {"msvcrt": fake_msvcrt}),
        patch(
            "figma_flutter_agent.debug.run_meta_lock.os.open",
            return_value=99,
        ),
        patch("figma_flutter_agent.debug.run_meta_lock.os.close") as close_mock,
    ):
        with pytest.raises(RunMetaStaleWriterError, match="lock timeout"):
            with run_meta_lifecycle_lock(meta_path, timeout_sec=0.01):
                pass

    unlock_calls = [
        call
        for call in fake_msvcrt.locking.call_args_list
        if call.args and call.args[1] == fake_msvcrt.LK_UNLCK
    ]
    assert not unlock_calls
    close_mock.assert_called_once_with(99)


def test_non_contention_oserror_is_not_swallowed(tmp_path: Path) -> None:
    meta_path = tmp_path / "screen" / "run.meta.json"
    meta_path.parent.mkdir(parents=True)

    fake_msvcrt = MagicMock()
    fake_msvcrt.LK_NBLCK = 8
    fake_msvcrt.locking.side_effect = OSError(13, "permission denied")

    with (
        patch.object(os, "name", "nt"),
        patch.dict("sys.modules", {"msvcrt": fake_msvcrt}),
        patch(
            "figma_flutter_agent.debug.run_meta_lock.os.open",
            return_value=99,
        ),
        patch("figma_flutter_agent.debug.run_meta_lock.os.close"),
    ):
        with pytest.raises(OSError, match="permission denied"):
            with run_meta_lifecycle_lock(meta_path, timeout_sec=1.0):
                pass
