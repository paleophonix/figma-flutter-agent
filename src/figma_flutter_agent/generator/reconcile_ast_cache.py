"""Per-pipeline-run cache for AST sidecar output (same source → skip subprocess)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field

_AST_SESSION: ContextVar[_AstCacheSession | None] = ContextVar(
    "figma_ast_reconcile_cache",
    default=None,
)


@dataclass
class _AstCacheSession:
    entries: dict[str, tuple[str, str]] = field(default_factory=dict)
    hits: int = 0
    subprocess_calls: int = 0


def begin_ast_reconcile_cache() -> None:
    _AST_SESSION.set(_AstCacheSession())


def end_ast_reconcile_cache() -> None:
    _AST_SESSION.set(None)


def ast_reconcile_cache_active() -> bool:
    return _AST_SESSION.get() is not None


def _source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def cached_ast_transform(path: str, pre_ast_source: str, transform: Callable[[str], str]) -> str:
    """Run ``transform`` once per (path, source); reuse output when the session cache is active."""
    session = _AST_SESSION.get()
    if session is None:
        return transform(pre_ast_source)
    key = path.replace("\\", "/")
    digest = _source_hash(pre_ast_source)
    hit = session.entries.get(key)
    if hit is not None and hit[0] == digest:
        session.hits += 1
        return hit[1]
    session.subprocess_calls += 1
    processed = transform(pre_ast_source)
    session.entries[key] = (digest, processed)
    return processed


def ast_reconcile_cache_stats() -> tuple[int, int, int]:
    """Return (cache_hits, unique_paths, subprocess_calls) for the active session."""
    session = _AST_SESSION.get()
    if session is None:
        return 0, 0, 0
    return session.hits, len(session.entries), session.subprocess_calls
