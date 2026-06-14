"""Capture Flutter render/layout errors into per-screen ``last.log``."""

from __future__ import annotations

import re
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.terminal_log import LastLogStreamSection
from figma_flutter_agent.dev.json_websocket import JsonWebSocket

_VM_SERVICE_URI_RE = re.compile(
    r"Debug service listening on (ws://\S+)",
    re.IGNORECASE,
)
_VM_SOCKET_TIMEOUT_SEC = 1.0
_RENDER_ERROR_MARKERS = (
    "overflowed",
    "renderflex",
    "renderbox",
    "renderobject",
    "another exception was thrown",
    "the following assertion",
    "assertion failed",
    "exception caught by",
    "during layout",
    "during paint",
    "lateinitializationerror",
    "typeerror",
    "nosuchmethoderror",
    "══╡",
    "══════",
)
_RENDER_ERROR_LINE_RE = re.compile(
    r"(?:^|\s)(?:error|exception|failed assertion|assertion error)\b",
    re.IGNORECASE,
)
_FLUTTER_ERROR_EXTENSION_KINDS = frozenset(
    {
        "Flutter.Error",
        "Flutter.Exception",
    }
)


def parse_vm_service_uri(line: str) -> str | None:
    """Extract a Dart VM Service WebSocket URI from a ``flutter run`` log line."""
    match = _VM_SERVICE_URI_RE.search(line)
    if match is None:
        return None
    return match.group(1).rstrip(").,")


def is_render_error_line(line: str) -> bool:
    """Return True when a ``flutter run`` line looks like a render/layout failure."""
    text = line.strip()
    if not text:
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in _RENDER_ERROR_MARKERS):
        return True
    return _RENDER_ERROR_LINE_RE.search(text) is not None


class FlutterRenderErrorCapture:
    """Collect render/layout errors while ``flutter run`` is active."""

    def __init__(self, *, sink: Callable[[str], None]) -> None:
        self._sink = sink
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._vm_started = False
        self._vm_lock = threading.Lock()

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=5.0)

    def feed_flutter_line(self, line: str) -> None:
        if is_render_error_line(line):
            self._emit(line)
        uri = parse_vm_service_uri(line)
        if uri is None:
            return
        with self._vm_lock:
            if self._vm_started:
                return
            self._vm_started = True
        thread = threading.Thread(
            target=self._run_vm_service,
            args=(uri,),
            name="flutter-vm-render-errors",
            daemon=True,
        )
        thread.start()
        self._threads.append(thread)

    def _emit(self, line: str) -> None:
        text = line.rstrip("\n")
        if not text:
            return
        self._sink(text)
        sys.stdout.write(f"[render] {text}\n")
        sys.stdout.flush()

    def _run_vm_service(self, uri: str) -> None:
        socket_client: JsonWebSocket | None = None
        try:
            socket_client = JsonWebSocket(uri, timeout_sec=_VM_SOCKET_TIMEOUT_SEC)
            socket_client.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "streamListen",
                    "params": {"streamId": "Stderr"},
                }
            )
            socket_client.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "2",
                    "method": "streamListen",
                    "params": {"streamId": "Extension"},
                }
            )
            while not self._stop.is_set():
                try:
                    payload = socket_client.recv_json()
                except TimeoutError:
                    continue
                except OSError:
                    break
                if payload is None:
                    break
                formatted = _format_vm_service_render_error(payload)
                if formatted:
                    self._emit(formatted)
        except Exception:
            logger.debug("Dart VM Service render-error capture stopped")
        finally:
            if socket_client is not None:
                socket_client.close()


def _format_vm_service_render_error(payload: dict[str, Any]) -> str:
    method = payload.get("method")
    params = payload.get("params")
    if method != "streamNotify" or not isinstance(params, dict):
        return ""
    event = params.get("event")
    if not isinstance(event, dict):
        return ""
    if event.get("type") == "WriteEvent":
        text = str(event.get("text", "")).rstrip("\n")
        return text if is_render_error_line(text) else ""
    extension = event.get("extensionData")
    if not isinstance(extension, dict):
        return ""
    kind = str(extension.get("extensionKind", ""))
    if kind not in _FLUTTER_ERROR_EXTENSION_KINDS:
        return ""
    data = extension.get("data")
    if isinstance(data, dict) and "message" in data:
        return f"{kind}: {data['message']}"
    return f"{kind}: {data}"


def open_render_error_log_stream(
    *,
    project_dir: Path,
    feature_name: str,
) -> LastLogStreamSection | None:
    """Open a rolling ``flutter render errors`` section in ``last.log``."""
    feature = feature_name.strip()
    if not feature:
        return None
    section = LastLogStreamSection(
        "flutter render errors",
        project_dir=project_dir,
        feature_name=feature,
    )
    section.open()
    return section
