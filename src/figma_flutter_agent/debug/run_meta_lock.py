"""Per-screen interprocess lock and atomic writes for ``run.meta.json``."""

from __future__ import annotations

import contextlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from figma_flutter_agent.errors import RunMetaStaleWriterError

_DEFAULT_LOCK_TIMEOUT_SEC = 600.0
_UTF8_ENCODING = "utf-8"


@contextlib.contextmanager
def run_meta_pair_lock(
    left: Path,
    right: Path,
    *,
    timeout_sec: float = _DEFAULT_LOCK_TIMEOUT_SEC,
):
    """Acquire two per-screen locks in deterministic path order (deadlock-safe)."""
    ordered = sorted({left, right}, key=lambda path: path.as_posix())
    if len(ordered) == 1:
        with run_meta_lifecycle_lock(ordered[0], timeout_sec=timeout_sec):
            yield
        return
    with run_meta_lifecycle_lock(ordered[0], timeout_sec=timeout_sec):
        with run_meta_lifecycle_lock(ordered[1], timeout_sec=timeout_sec):
            yield


@contextlib.contextmanager
def run_meta_lifecycle_lock(meta_path: Path, *, timeout_sec: float = _DEFAULT_LOCK_TIMEOUT_SEC):
    """Serialize run.meta read-modify-write across processes for one screen."""
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = meta_path.parent / ".run_meta.lock"
    deadline = time.monotonic() + timeout_sec
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    msg = f"run.meta lock timeout for {meta_path.parent.as_posix()}"
                    raise RunMetaStaleWriterError(msg) from None
                time.sleep(0.02)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def atomic_write_run_meta_dict(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace run.meta using a unique temp file per writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(content, encoding=_UTF8_ENCODING)
        tmp_path.replace(path)
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
