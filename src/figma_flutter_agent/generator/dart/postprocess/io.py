"""UTF-8 Dart source I/O."""

from __future__ import annotations

from pathlib import Path

UTF8_ENCODING = "utf-8"


def read_dart_source(path: Path) -> str:
    return path.read_text(encoding=UTF8_ENCODING)


def write_dart_source(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding=UTF8_ENCODING)
