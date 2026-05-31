"""AST reconcile cache session summary."""

import io

from loguru import logger

from figma_flutter_agent.generator.reconcile_ast_cache import (
    ast_reconcile_cache_stats,
    begin_ast_reconcile_cache,
    cached_ast_transform,
    end_ast_reconcile_cache,
)
from figma_flutter_agent.observability import log_ast_reconcile_session_summary


def test_log_ast_reconcile_session_summary() -> None:
    stream = io.StringIO()
    sink_id = logger.add(stream, format="{message}")
    bound = logger.bind(run_id="test")
    begin_ast_reconcile_cache()
    try:
        cached_ast_transform("lib/a.dart", "a", lambda s: s.upper())
        cached_ast_transform("lib/a.dart", "a", lambda s: s.upper())
        log_ast_reconcile_session_summary(bound)
        hits, paths, subprocess = ast_reconcile_cache_stats()
        assert hits == 1
        assert paths == 1
        assert subprocess == 1
    finally:
        logger.remove(sink_id)
        end_ast_reconcile_cache()

    output = stream.getvalue()
    assert "AST reconcile cache (run): 1 subprocess call(s), 1 cache hit(s), 1 unique path(s)" in output
