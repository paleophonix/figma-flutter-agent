"""Tests for fetch/parse pipeline stages."""

import json
from pathlib import Path

from figma_flutter_agent.parser.prototype import collect_prototype_links, index_frames
from figma_flutter_agent.stages.fetch import FigmaFetchResult
from figma_flutter_agent.stages.parse import parse_figma_frame


def test_parse_figma_frame_from_fixture() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    fetch = FigmaFetchResult(
        file_key="fixture",
        node_id="1:1",
        root=root,
        variables_payload=None,
        published_styles={},
        components={},
        prototype_links=collect_prototype_links(root),
        frame_index=index_frames(root),
    )

    result = parse_figma_frame(fetch)

    assert result.clean_tree.name
    assert result.tokens.colors
    assert isinstance(result.cluster_summary, dict)
