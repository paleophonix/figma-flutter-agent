"""Tests for pipeline stage logging."""

import inspect
import io

from loguru import logger

from figma_flutter_agent.generator.layout.flex_policy.stack import (
    stack_flow_child_needs_vertical_extent_bind,
)
from figma_flutter_agent.observability import log_stage
from figma_flutter_agent.observability.api_contract import api_contract_drift_from_type_error
from figma_flutter_agent.wizard.run_actions import report_plan_failure_stale_preview


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


def test_stack_flow_child_needs_vertical_extent_bind_accepts_emitter_kwargs() -> None:
    """Stack emitters must call policy helper with parent/responsive context."""
    params = inspect.signature(stack_flow_child_needs_vertical_extent_bind).parameters
    assert "parent_node" in params
    assert "responsive_enabled" in params


def test_api_contract_drift_from_type_error() -> None:
    """Unexpected-kwarg TypeErrors are classified for plan-stage diagnostics."""
    exc = TypeError(
        "stack_flow_child_needs_vertical_extent_bind() got an unexpected keyword argument 'parent_node'"
    )
    drift = api_contract_drift_from_type_error(exc)
    assert drift is not None
    assert drift["kind"] == "api_contract_drift"
    assert drift["callee"] == "stack_flow_child_needs_vertical_extent_bind"
    assert drift["unexpected_kwarg"] == "parent_node"


def test_log_stage_classifies_api_contract_drift_type_error() -> None:
    stream = io.StringIO()
    sink_id = logger.add(stream, format="{message}")
    bound = logger.bind(file_key="test")
    try:
        with log_stage(bound, "plan"):
            raise TypeError(
                "stack_flow_child_needs_vertical_extent_bind() got an unexpected keyword argument 'parent_node'"
            )
    except TypeError:
        pass
    finally:
        logger.remove(sink_id)

    output = stream.getvalue()
    assert "api_contract_drift" in output
    assert "stack_flow_child_needs_vertical_extent_bind" in output


def test_report_plan_failure_stale_preview_message(capsys) -> None:
    """Wizard must mark Chrome preview stale when codegen aborts before writeback."""
    report_plan_failure_stale_preview()
    captured = capsys.readouterr().out
    assert "stale" in captured.lower()
    assert "writeback: skipped" in captured
