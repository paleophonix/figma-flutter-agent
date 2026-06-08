"""Write batch models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WriteRecord:
    target: Path
    existed_before: bool


@dataclass(frozen=True)
class WriteBatch:
    """Pending write batch that can be committed or rolled back."""

    backup_dir: Path
    written: list[WriteRecord]
