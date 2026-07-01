"""Acceptance tests mapped to spec §23 criteria."""

import json
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.validation.spec23.evaluate import evaluate_spec23
from figma_flutter_agent.validation.spec23.models import Spec23Report


@pytest.mark.parametrize(
    "fixture_name",
    [
        "figma_node_sample.json",
        "figma_cards_sample.json",
        "figma_carousel_sample.json",
        "figma_bottom_nav_sample.json",
    ],
)
def test_spec23_evaluator_passes_for_fixture(fixture_name: str) -> None:
    root = json.loads(Path(f"tests/fixtures/{fixture_name}").read_text(encoding="utf-8"))
    report = evaluate_spec23(root, Settings(), node_id=root["id"], strict=True)

    assert report.passed, _format_report(report)


def test_spec23_report_lists_all_criteria() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    report = evaluate_spec23(root, Settings(), node_id=root["id"], strict=True)

    assert len(report.criteria) == 11
    assert {item.name for item in report.criteria} == {
        "figma_connectivity",
        "rest_css_synthesis",
        "responsive_flutter_ui",
        "reusable_widgets",
        "design_system",
        "asset_export",
        "responsive_layouts",
        "flutter_optimization",
        "production_ready_code",
        "developer_changes_preserved",
        "emit_fidelity_contracts",
    }


def _format_report(report: Spec23Report) -> str:
    failed = [item for item in report.criteria if not item.passed]
    return "; ".join(f"{item.name}: {item.detail}" for item in failed)


def test_spec23_connectivity_live_fetch_success() -> None:
    from unittest.mock import patch

    from figma_flutter_agent.figma.client import FigmaConnector
    from figma_flutter_agent.validation.spec23.figma import _criterion_figma_connectivity

    async def mock_fetch(*args: object, **kwargs: object) -> None:
        pass

    @patch.dict(
        "os.environ",
        {
            "FIGMA_ACCESS_TOKEN": "test_token",
            "FIGMA_SMOKE_FILE_KEY": "test_file",
            "FIGMA_SMOKE_NODE_ID": "1:1",
        },
        clear=False,
    )
    @patch.object(FigmaConnector, "fetch_nodes", side_effect=mock_fetch)
    def run_test(mock_fetch_nodes: object) -> None:
        res = _criterion_figma_connectivity(strict=True, settings=Settings())

        assert res.passed
        assert "live fetch OK" in res.detail
        assert "1:1" in res.detail

    run_test()


def test_spec23_developer_changes_strict_uses_dart_writer() -> None:
    from figma_flutter_agent.validation.spec23.preservation import (
        _criterion_developer_changes_preserved,
    )

    strict = _criterion_developer_changes_preserved(strict=True)
    non_strict = _criterion_developer_changes_preserved(strict=False)

    assert strict.passed
    assert strict.detail == "DartWriter regen"
    assert non_strict.passed
    assert non_strict.detail == "merge_custom_code"


def test_spec23_connectivity_live_fetch_failure() -> None:
    from unittest.mock import patch

    from figma_flutter_agent.figma.client import FigmaConnector
    from figma_flutter_agent.validation.spec23.figma import _criterion_figma_connectivity

    async def fail_fetch(*args: object, **kwargs: object) -> None:
        raise Exception("API error")

    @patch.dict(
        "os.environ",
        {
            "FIGMA_ACCESS_TOKEN": "test_token",
            "FIGMA_SMOKE_FILE_KEY": "test_file",
            "FIGMA_SMOKE_NODE_ID": "1:1",
        },
    )
    @patch.object(FigmaConnector, "fetch_nodes", side_effect=fail_fetch)
    def run_test(mock_fetch_nodes: object) -> None:
        res = _criterion_figma_connectivity(strict=True)

        assert not res.passed
        assert "live fetch failed" in res.detail
        assert "API error" in res.detail

    run_test()
