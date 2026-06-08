"""UTF-8 file IO helpers for generated files."""

from __future__ import annotations

from pathlib import Path

_UTF8_ENCODING = "utf-8"


def read_text_file(path: Path) -> str:
    """Read a project text file as UTF-8."""
    return path.read_text(encoding=_UTF8_ENCODING)


def atomic_write_text(target: Path, content: str) -> None:
    tmp_path = target.with_name(f"{target.name}.tmp")
    try:
        tmp_path.write_text(content, encoding=_UTF8_ENCODING)
        tmp_path.replace(target)
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
