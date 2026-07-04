"""run.meta lock behavior tests."""

from __future__ import annotations

import errno
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from figma_flutter_agent.debug.run_meta_lock import run_meta_lifecycle_lock
from figma_flutter_agent.errors import RunMetaStaleWriterError


def _windows_lock_timeout_setup(
    *,
    contention_errno: int,
    contention_message: str,
) -> tuple[Path, MagicMock]:
    meta_path = Path("/tmp/screen/run.meta.json")
    fake_msvcrt = MagicMock()
    fake_msvcrt.LK_NBLCK = 8
    fake_msvcrt.LK_UNLCK = 9
    fake_msvcrt.locking.side_effect = OSError(contention_errno, contention_message)
    return meta_path, fake_msvcrt


def test_lock_timeout_does_not_attempt_unlock_when_never_acquired() -> None:
    meta_path, fake_msvcrt = _windows_lock_timeout_setup(
        contention_errno=errno.EACCES,
        contention_message="permission denied",
    )

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
        patch.object(Path, "mkdir"),
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


def test_lock_timeout_treats_edeadlk_as_contention() -> None:
    meta_path, fake_msvcrt = _windows_lock_timeout_setup(
        contention_errno=errno.EDEADLK,
        contention_message="resource deadlock would occur",
    )

    with (
        patch.object(os, "name", "nt"),
        patch("figma_flutter_agent.debug.run_meta_lock.time.monotonic", side_effect=[0.0, 1.0]),
        patch.dict("sys.modules", {"msvcrt": fake_msvcrt}),
        patch(
            "figma_flutter_agent.debug.run_meta_lock.os.open",
            return_value=99,
        ),
        patch("figma_flutter_agent.debug.run_meta_lock.os.close"),
        patch.object(Path, "mkdir"),
    ):
        with pytest.raises(RunMetaStaleWriterError, match="lock timeout"):
            with run_meta_lifecycle_lock(meta_path, timeout_sec=0.01):
                pass


def test_non_contention_oserror_is_not_swallowed() -> None:
    meta_path, fake_msvcrt = _windows_lock_timeout_setup(
        contention_errno=errno.EINVAL,
        contention_message="invalid argument",
    )

    with (
        patch.object(os, "name", "nt"),
        patch.dict("sys.modules", {"msvcrt": fake_msvcrt}),
        patch(
            "figma_flutter_agent.debug.run_meta_lock.os.open",
            return_value=99,
        ),
        patch("figma_flutter_agent.debug.run_meta_lock.os.close"),
        patch.object(Path, "mkdir"),
    ):
        with pytest.raises(OSError, match="invalid argument"):
            with run_meta_lifecycle_lock(meta_path, timeout_sec=1.0):
                pass
