"""Hard stage deadline worker (Program 10 P1-a)."""

from __future__ import annotations

import multiprocessing as mp
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def _spawn_target(
    result_queue: mp.Queue,
    fn: Callable[[], T],
) -> None:
    try:
        result_queue.put(("ok", fn()))
    except Exception as exc:  # noqa: BLE001 — IPC boundary
        result_queue.put(("err", repr(exc)))


def run_with_spawn_deadline(
    fn: Callable[[], T],
    *,
    timeout_sec: float,
    stage_name: str,
) -> T:
    """Run picklable ``fn`` in a spawn worker; terminate→kill on deadline."""
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=_spawn_target,
        args=(queue, fn),
        name=f"stage-{stage_name}",
    )
    process.start()
    process.join(timeout_sec)
    if process.is_alive():
        process.terminate()
        process.join(1.0)
        if process.is_alive():
            process.kill()
            process.join(1.0)
        raise TimeoutError(f"Stage {stage_name} exceeded hard deadline {timeout_sec}s")
    if queue.empty():
        raise RuntimeError(f"Stage {stage_name} worker exited without result")
    kind, payload = queue.get_nowait()
    if kind == "err":
        raise RuntimeError(f"Stage {stage_name} failed: {payload}")
    return payload  # type: ignore[return-value]
