"""Tests for pipeline stage logging."""

import io

from loguru import logger

from figma_flutter_agent.observability import log_stage


def test_log_stage_completes_without_error() -> None:
    bound = logger.bind(file_key="test")
    with log_stage(bound, "unit_test"):
        pass


def test_log_stage_logs_failed_on_exception() -> None:
    stream = io.StringIO()
    sink_id = logger.add(stream, format="{message}")
    bound = logger.bind(file_key="test")
    try:
        with log_stage(bound, "unit_test"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    finally:
        logger.remove(sink_id)

    output = stream.getvalue()
    assert "Stage unit_test failed" in output
    assert "Stage unit_test completed" not in output
