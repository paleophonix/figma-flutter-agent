"""Subprocess helpers with timeouts so pipeline stages cannot hang indefinitely."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from loguru import logger

_FLUTTER_TEST_PROGRESS = re.compile(r"^\d{2}:\d{2} \+(\d+): (.+)$")
_FLUTTER_TEST_PROGRESS_THROTTLE_SEC = 20.0
_SUBPROCESS_STREAM_DRAIN_JOIN_SEC = 30.0
_FLUTTER_STACK_FRAME = re.compile(r"^#\d+\s+")
_SUBPROCESS_OUTPUT_SUMMARY_MAX_CHARS = 4000
_NOISY_SUBPROCESS_PREFIXES = (
    "The following RenderObject was being processed",
    "This RenderObject had the following descendants",
    "When the exception was thrown, this was the stack:",
    "Either the assertion indicates",
    "more information in this error message",
    "In either case, please report",
    "See also: https://flutter.dev",
)
_NOISY_RENDER_DUMP_KEYS = (
    "creator:",
    "parentData:",
    "constraints:",
    "size:",
    "direction:",
    "mainAxisAlignment:",
    "mainAxisSize:",
    "crossAxisAlignment:",
    "verticalDirection:",
    "spacing:",
    "additionalConstraints:",
)

# Keep in sync with repair / write / golden capture expectations.
DART_FORMAT_TIMEOUT_SEC = 90.0
FLUTTER_PUB_GET_TIMEOUT_SEC = 180.0
FLUTTER_ANALYZE_TIMEOUT_SEC = 300.0
DART_ANALYZE_TIMEOUT_SEC = 120.0
FLUTTER_TEST_TIMEOUT_SEC = 600.0
BUILD_RUNNER_TIMEOUT_SEC = 600.0
DOCKER_COMPOSE_TIMEOUT_SEC = 900.0
_TERMINATE_WAIT_SEC = 5.0
_SUBPROCESS_TEXT_ENCODING = "utf-8"
_SUBPROCESS_ENCODING_ERRORS = "replace"


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    """Force-stop a subprocess and any children (Windows ``dart`` spawns helpers)."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
            encoding=_SUBPROCESS_TEXT_ENCODING,
            errors=_SUBPROCESS_ENCODING_ERRORS,
            check=False,
        )
        return
    proc.terminate()


def _flutter_test_progress_key(line: str) -> str | None:
    """Return a stable key for compact-reporter tick lines, or None when not a tick."""
    match = _FLUTTER_TEST_PROGRESS.match(line.strip())
    if match is None:
        return None
    return f"+{match.group(1)}: {match.group(2)}"


def is_noisy_subprocess_stream_line(line: str) -> bool:
    """Return True for low-signal flutter test stack/dump lines (still captured in buffers)."""
    stripped = line.strip()
    if not stripped:
        return True
    if _FLUTTER_STACK_FRAME.match(stripped):
        return True
    if stripped == "<asynchronous suspension>":
        return True
    if stripped.startswith("(elided "):
        return True
    if stripped.startswith("══") or stripped.startswith("╡"):
        if "EXCEPTION CAUGHT BY" not in stripped:
            return True
    if "github.com/flutter/flutter/issues" in stripped:
        return True
    if any(stripped.startswith(prefix) for prefix in _NOISY_SUBPROCESS_PREFIXES):
        return True
    if stripped.startswith("'package:flutter/") and stripped.endswith("'"):
        return True
    if line.startswith(("  ", "\t")):
        trimmed = line.strip()
        if trimmed.startswith("child ") and ": Render" in trimmed:
            return True
        if any(trimmed.startswith(key) for key in _NOISY_RENDER_DUMP_KEYS):
            return True
    return False


def summarize_subprocess_output(
    combined: str,
    *,
    max_chars: int = _SUBPROCESS_OUTPUT_SUMMARY_MAX_CHARS,
) -> str:
    """Collapse flutter test failures to high-signal lines for logs."""
    kept: list[str] = []
    for line in combined.splitlines():
        if is_noisy_subprocess_stream_line(line):
            continue
        stripped = line.strip()
        if not stripped:
            continue
        kept.append(line.rstrip())
    if not kept:
        stripped = combined.strip()
        if len(stripped) <= max_chars:
            return stripped
        return stripped[-max_chars:]
    summary = "\n".join(kept)
    if len(summary) <= max_chars:
        return summary
    return summary[-max_chars:]


def _should_log_stream_line(line: str, throttle_state: dict[str, Any]) -> bool:
    """Drop repeated flutter test progress ticks and render-tree noise."""
    if is_noisy_subprocess_stream_line(line):
        return False
    stripped = line.strip()
    if "EXCEPTION CAUGHT BY" in stripped:
        last_banner = throttle_state.get("last_exception_banner")
        if last_banner == stripped:
            return False
        throttle_state["last_exception_banner"] = stripped
    key = _flutter_test_progress_key(line)
    if key is None:
        throttle_state.pop("flutter_progress_key", None)
        return True
    now = time.monotonic()
    last_key = throttle_state.get("flutter_progress_key")
    last_logged = float(throttle_state.get("flutter_progress_logged_at", 0.0))
    if last_key == key and now - last_logged < _FLUTTER_TEST_PROGRESS_THROTTLE_SEC:
        return False
    throttle_state["flutter_progress_key"] = key
    throttle_state["flutter_progress_logged_at"] = now
    return True


def _stream_subprocess_output(
    proc: subprocess.Popen[str],
    *,
    label: str,
    stop: threading.Event,
) -> tuple[list[str], list[str], list[threading.Thread]]:
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    throttle_state: dict[str, Any] = {}

    def consume(pipe, bucket: list[str]) -> None:
        if pipe is None:
            return
        for line in pipe:
            if stop.is_set():
                break
            stripped = line.rstrip()
            if not stripped:
                continue
            bucket.append(stripped)
            if _should_log_stream_line(stripped, throttle_state):
                logger.info("[{}] {}", label, stripped)

    threads = [
        threading.Thread(
            target=consume,
            args=(proc.stdout, stdout_lines),
            daemon=True,
        ),
    ]
    if proc.stderr is not None and proc.stderr is not proc.stdout:
        threads.append(
            threading.Thread(
                target=consume,
                args=(proc.stderr, stderr_lines),
                daemon=True,
            ),
        )
    for thread in threads:
        thread.start()
    return stdout_lines, stderr_lines, threads


def run_interactive_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
    label: str,
    log: bool = True,
    env: Mapping[str, str] | None = None,
    project_dir: Path | None = None,
    feature_name: str | None = None,
    on_stdout_line: Callable[[str], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a long-lived CLI command with inherited stdin and tee stdout to the terminal.

    Child stdout/stderr are captured for ``last.log`` while still streaming to the
    interactive terminal (for example ``flutter run`` hot reload).

    Args:
        command: argv for the child process.
        cwd: Working directory.
        label: Short description stored in ``last.log``.
        log: When False, skip start/finish log lines.
        env: Optional extra environment variables merged onto ``os.environ``.
        project_dir: Flutter project root for ``last.log`` routing.
        feature_name: Active screen slug for ``last.log`` routing.

    Returns:
        Completed process (non-zero exit codes are not raised).
    """
    argv = list(command)
    if log:
        logger.info("Running {} (interactive)", label)
    popen_env = None
    if env is not None:
        popen_env = {**os.environ, **dict(env)}
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=popen_env,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=_SUBPROCESS_TEXT_ENCODING,
        errors=_SUBPROCESS_ENCODING_ERRORS,
        bufsize=1,
    )
    stdout_lines: list[str] = []
    if proc.stdout is not None:
        for line in proc.stdout:
            stripped = line.rstrip("\n")
            stdout_lines.append(stripped)
            sys.stdout.write(line)
            sys.stdout.flush()
            if on_stdout_line is not None:
                on_stdout_line(stripped)
    returncode = proc.wait()
    stdout = "\n".join(stdout_lines)
    if log:
        logger.info("{} finished with exit code {}", label, returncode)
    from figma_flutter_agent.debug.terminal_log import append_terminal_output

    append_terminal_output(
        label,
        stdout=stdout,
        exit_code=returncode,
        project_dir=project_dir,
        feature_name=feature_name,
    )
    return subprocess.CompletedProcess(argv, returncode, stdout, "")


def _heartbeat_while_running(
    proc: subprocess.Popen[str],
    *,
    label: str,
    interval_sec: float,
    stop: threading.Event,
) -> None:
    while not stop.wait(interval_sec):
        if proc.poll() is not None:
            return
        logger.info("{} still running…", label)


def run_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
    label: str,
    timeout_sec: float,
    log: bool = True,
    stream_output: bool = False,
    env: Mapping[str, str] | None = None,
    timeout_log_level: str = "error",
    project_dir: Path | None = None,
    feature_name: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a CLI command with a hard timeout and process-tree termination.

    Args:
        command: argv for the child process.
        cwd: Working directory.
        label: Short description for logs (for example ``flutter pub get``).
        timeout_sec: Maximum wall time in seconds.
        log: When False, skip start/finish log lines (batch callers log progress).
        stream_output: When True, log child stdout/stderr lines as they arrive.
        env: Optional extra environment variables merged onto ``os.environ``.
        timeout_log_level: Loguru level for timeout kills (``warning`` for recoverable).
        project_dir: Flutter project root for ``last.log`` routing.
        feature_name: Active screen slug for ``last.log`` routing.

    Returns:
        Completed process (non-zero exit codes are not raised).

    Raises:
        subprocess.TimeoutExpired: When the command exceeds ``timeout_sec``.
    """
    argv = list(command)
    timeout_log = getattr(logger, timeout_log_level, logger.error)
    if log:
        logger.info("Running {} (timeout {:.0f}s)", label, timeout_sec)
    popen_env = None
    if env is not None:
        popen_env = {**os.environ, **dict(env)}
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=popen_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if stream_output else subprocess.PIPE,
        text=True,
        encoding=_SUBPROCESS_TEXT_ENCODING,
        errors=_SUBPROCESS_ENCODING_ERRORS,
        bufsize=1,
    )
    if stream_output:
        stop = threading.Event()
        heartbeat = threading.Thread(
            target=_heartbeat_while_running,
            args=(proc,),
            kwargs={"label": label, "interval_sec": 45.0, "stop": stop},
            daemon=True,
        )
        heartbeat.start()
        stdout_lines, stderr_lines, stream_threads = _stream_subprocess_output(
            proc,
            label=label,
            stop=stop,
        )
        deadline = time.monotonic() + timeout_sec
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                stop.set()
                timeout_log(
                    "{} timed out after {:.0f}s; killing process tree",
                    label,
                    timeout_sec,
                )
                _terminate_process_tree(proc)
                proc.wait(timeout=_TERMINATE_WAIT_SEC)
                for thread in stream_threads:
                    thread.join(timeout=_SUBPROCESS_STREAM_DRAIN_JOIN_SEC)
                raise subprocess.TimeoutExpired(
                    cmd=argv,
                    timeout=timeout_sec,
                    output="\n".join(stdout_lines),
                    stderr="\n".join(stderr_lines),
                )
            time.sleep(0.25)
        for thread in stream_threads:
            thread.join(timeout=_SUBPROCESS_STREAM_DRAIN_JOIN_SEC)
        stop.set()
        for thread in stream_threads:
            thread.join(timeout=5.0)
        heartbeat.join(timeout=1.0)
        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)
        returncode = proc.returncode if proc.returncode is not None else 1
    else:
        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired as exc:
            timeout_log(
                "{} timed out after {:.0f}s; killing process tree",
                label,
                timeout_sec,
            )
            _terminate_process_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=_TERMINATE_WAIT_SEC)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate(timeout=_TERMINATE_WAIT_SEC)
            raise subprocess.TimeoutExpired(
                cmd=argv, timeout=timeout_sec, output=stdout, stderr=stderr
            ) from exc
        returncode = proc.returncode if proc.returncode is not None else 1
    if log:
        logger.info("{} finished with exit code {}", label, returncode)
    from figma_flutter_agent.debug.terminal_log import append_terminal_output

    append_terminal_output(
        label,
        stdout=stdout or "",
        stderr=stderr or "",
        exit_code=returncode,
        project_dir=project_dir,
        feature_name=feature_name,
    )
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
