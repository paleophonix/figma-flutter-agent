"""Emitter and IR schema versions stamped into debug dumps and cache metadata."""

from __future__ import annotations

EMITTER_VERSION = "2026.07.1"

# Bump when ScreenIr shape, cached IR required fields, or reader semantics change
# incompatibly. Optional metadata additions safe for old readers do not require bump.
IR_SCHEMA_VERSION = "1"
