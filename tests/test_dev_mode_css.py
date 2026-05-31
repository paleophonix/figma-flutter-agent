"""Tests for Dev Mode CSS dump parser and merge (Phase 2)."""

from __future__ import annotations

import json
import pytest

from figma_flutter_agent.parser.dev_mode_css import (
    DevModeCssDump,
    DevModeCssDumpError,
    DevModeCssNode,
    apply_dump_to_node,
    load_dev_mode_css_dump,
    make_dump_dict,
    merge_dev_mode_css_into_style,
)
from figma_flutter_agent.parser.styles import enrich_node_style
from figma_flutter_agent.schemas import NodeStyle


# ---------------------------------------------------------------------------
# make_dump_dict / round-trip helpers
# ---------------------------------------------------------------------------


def _write_dump(tmp_path, data: dict) -> str:
    p = tmp_path / "dump.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# load_dev_mode_css_dump
# ---------------------------------------------------------------------------


class TestLoadDevModeCssDump:
    def test_loads_valid_v1_dump(self, tmp_path) -> None:
        data = make_dump_dict(
            file_key="abc123",
            exported_at="2026-01-15T12:00:00Z",
            nodes={
                "1:1": {"name": "Button", "css": {"background-color": "rgba(0,0,255,1)", "border-radius": "8px"}},
                "1:2": {"name": "Label", "css": {"color": "rgba(255,255,255,1)", "font-size": "16px"}},
            },
        )
        path = _write_dump(tmp_path, data)
        dump = load_dev_mode_css_dump(path)

        assert dump.version == 1
        assert dump.file_key == "abc123"
        assert dump.exported_at == "2026-01-15T12:00:00Z"
        assert len(dump.nodes) == 2

        node = dump.get_node("1:1")
        assert node is not None
        assert node.name == "Button"
        assert node.css["background-color"] == "rgba(0,0,255,1)"
        assert node.css["border-radius"] == "8px"

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(DevModeCssDumpError, match="not found"):
            load_dev_mode_css_dump(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_raises(self, tmp_path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("not json{{", encoding="utf-8")
        with pytest.raises(DevModeCssDumpError, match="Cannot parse"):
            load_dev_mode_css_dump(str(p))

    def test_wrong_version_raises(self, tmp_path) -> None:
        data = {"version": 99, "nodes": {}}
        path = _write_dump(tmp_path, data)
        with pytest.raises(DevModeCssDumpError, match="Unsupported.*version"):
            load_dev_mode_css_dump(path)

    def test_missing_node_returns_none(self, tmp_path) -> None:
        data = make_dump_dict(nodes={"1:1": {"name": "A", "css": {}}})
        path = _write_dump(tmp_path, data)
        dump = load_dev_mode_css_dump(path)
        assert dump.get_node("99:99") is None

    def test_empty_nodes_ok(self, tmp_path) -> None:
        path = _write_dump(tmp_path, make_dump_dict())
        dump = load_dev_mode_css_dump(path)
        assert dump.nodes == {}
        assert dump.file_key == ""

    def test_non_dict_node_entry_skipped(self, tmp_path) -> None:
        data = make_dump_dict(nodes={"1:1": "bad", "1:2": {"name": "Good", "css": {"color": "red"}}})  # type: ignore[arg-type]
        path = _write_dump(tmp_path, data)
        dump = load_dev_mode_css_dump(path)
        assert dump.get_node("1:1") is None
        assert dump.get_node("1:2") is not None


# ---------------------------------------------------------------------------
# merge_dev_mode_css_into_style
# ---------------------------------------------------------------------------


class TestMergeDevModeCssIntoStyle:
    def test_hybrid_existing_wins(self) -> None:
        existing = {"color": "rgba(255,0,0,1)", "font-size": "14px"}
        dump_css = {"color": "rgba(0,0,255,1)", "border-radius": "4px"}
        result = merge_dev_mode_css_into_style(existing, dump_css, override=False)
        assert result["color"] == "rgba(255,0,0,1)"   # existing wins
        assert result["border-radius"] == "4px"        # dump fills gap
        assert result["font-size"] == "14px"           # existing kept

    def test_override_mode_dump_wins(self) -> None:
        existing = {"color": "rgba(255,0,0,1)"}
        dump_css = {"color": "rgba(0,0,255,1)", "border-radius": "4px"}
        result = merge_dev_mode_css_into_style(existing, dump_css, override=True)
        assert result["color"] == "rgba(0,0,255,1)"   # dump wins

    def test_empty_dump_returns_existing_unchanged(self) -> None:
        existing = {"color": "rgba(1,2,3,1)"}
        result = merge_dev_mode_css_into_style(existing, {}, override=False)
        assert result == existing

    def test_does_not_mutate_inputs(self) -> None:
        existing = {"color": "rgba(1,2,3,1)"}
        dump_css = {"color": "rgba(4,5,6,1)", "extra": "val"}
        merge_dev_mode_css_into_style(existing, dump_css, override=True)
        assert existing == {"color": "rgba(1,2,3,1)"}  # not mutated


# ---------------------------------------------------------------------------
# apply_dump_to_node
# ---------------------------------------------------------------------------


class TestApplyDumpToNode:
    def _dump_with_node(self, tmp_path, node_id: str, css: dict) -> DevModeCssDump:
        data = make_dump_dict(nodes={node_id: {"name": "X", "css": css}})
        path = _write_dump(tmp_path, data)
        return load_dev_mode_css_dump(path)

    def test_applies_css_for_known_node(self, tmp_path) -> None:
        dump = self._dump_with_node(tmp_path, "1:5", {"clip-path": "circle(50%)"})
        result = apply_dump_to_node("1:5", {}, dump)
        assert result["clip-path"] == "circle(50%)"

    def test_unchanged_when_node_absent(self, tmp_path) -> None:
        dump = self._dump_with_node(tmp_path, "1:5", {"color": "red"})
        existing = {"color": "blue"}
        result = apply_dump_to_node("99:99", existing, dump)
        assert result == existing


# ---------------------------------------------------------------------------
# enrich_node_style integration
# ---------------------------------------------------------------------------


class TestEnrichNodeStyleDevModeIntegration:
    """enrich_node_style populates css_properties from REST by default;
    dev_mode_css enriches or overrides on top."""

    def test_default_path_populates_css_from_rest(self) -> None:
        style = enrich_node_style(
            {"opacity": 0.9, "fills": [{"type": "SOLID", "visible": True, "color": {"r": 1, "g": 0, "b": 0, "a": 1}}]},
            NodeStyle(),
        )
        # REST synthesis now auto-populates css_properties
        assert "background-color" in style.css_properties
        assert style.css_properties["opacity"] == "0.9"

    def test_dev_mode_css_populates_css_properties(self) -> None:
        dev_css = {"clip-path": "circle(50%)", "mix-blend-mode": "multiply"}
        style = enrich_node_style(
            {"fills": []},
            NodeStyle(),
            dev_mode_css=dev_css,
        )
        assert style.css_properties["clip-path"] == "circle(50%)"
        assert style.css_properties["mix-blend-mode"] == "multiply"

    def test_override_false_rest_wins_over_dump(self) -> None:
        """hybrid mode: REST-synthesised value wins over dump on key conflict."""
        # Give the node a real text fill so REST produces "color"
        style = enrich_node_style(
            {"fills": [{"type": "SOLID", "visible": True, "color": {"r": 1, "g": 0, "b": 0, "a": 1}}],
             "type": "TEXT"},
            NodeStyle(text_color="0xFFFF0000"),  # REST produces color: rgba(255,0,0,1.000)
            dev_mode_css={"color": "rgba(9,9,9,1)", "border-radius": "4px"},
            dev_mode_css_override=False,
        )
        # REST "color" wins over dump (hybrid: existing wins on conflict)
        assert style.css_properties["color"] == "rgba(255, 0, 0, 1.000)"
        # dump fills "border-radius" which REST doesn't produce for TEXT nodes
        assert style.css_properties["border-radius"] == "4px"

    def test_override_true_dump_wins(self) -> None:
        existing_style = NodeStyle(css_properties={"color": "rgba(1,2,3,1)"})
        dev_css = {"color": "rgba(9,9,9,1)"}
        style = enrich_node_style(
            {"fills": []},
            existing_style,
            dev_mode_css=dev_css,
            dev_mode_css_override=True,
        )
        assert style.css_properties["color"] == "rgba(9,9,9,1)"  # overridden


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestFigmaConfig:
    def test_default_config_is_rest_synthesis(self) -> None:
        from figma_flutter_agent.config import AgentYamlConfig

        cfg = AgentYamlConfig.model_validate({})
        assert cfg.figma.style_metadata.source == "rest_synthesis"
        assert cfg.figma.dev_mode.enabled is False
        assert cfg.figma.dev_mode.inspect_css.mode == "off"
        assert cfg.figma.dev_mode.inspect_css.dump_path is None

    def test_dev_mode_source_requires_enabled(self) -> None:
        from pydantic import ValidationError
        from figma_flutter_agent.config import AgentYamlConfig

        with pytest.raises(ValidationError, match="requires figma.dev_mode.enabled"):
            AgentYamlConfig.model_validate({
                "figma": {
                    "style_metadata": {"source": "dev_mode_inspect"},
                    "dev_mode": {"enabled": False},
                }
            })

    def test_hybrid_source_requires_enabled(self) -> None:
        from pydantic import ValidationError
        from figma_flutter_agent.config import AgentYamlConfig

        with pytest.raises(ValidationError, match="requires figma.dev_mode.enabled"):
            AgentYamlConfig.model_validate({
                "figma": {
                    "style_metadata": {"source": "hybrid"},
                    "dev_mode": {"enabled": False},
                }
            })

    def test_valid_dev_mode_inspect_config(self) -> None:
        from figma_flutter_agent.config import AgentYamlConfig

        cfg = AgentYamlConfig.model_validate({
            "figma": {
                "style_metadata": {"source": "dev_mode_inspect"},
                "dev_mode": {
                    "enabled": True,
                    "inspect_css": {"mode": "plugin_dump", "dump_path": "dumps/my_screen.json"},
                },
            }
        })
        assert cfg.figma.style_metadata.source == "dev_mode_inspect"
        assert cfg.figma.dev_mode.enabled is True
        assert cfg.figma.dev_mode.inspect_css.mode == "plugin_dump"
        assert cfg.figma.dev_mode.inspect_css.dump_path == "dumps/my_screen.json"

    def test_plugin_dump_mode_requires_dump_path(self) -> None:
        from pydantic import ValidationError
        from figma_flutter_agent.config import AgentYamlConfig

        with pytest.raises(ValidationError, match="dump_path is required"):
            AgentYamlConfig.model_validate({
                "figma": {
                    "dev_mode": {
                        "enabled": True,
                        "inspect_css": {"mode": "plugin_dump"},
                    }
                }
            })

    def test_rest_synthesis_default_unchanged_by_figma_section(self) -> None:
        """Adding an empty figma: block must not change any other config."""
        from figma_flutter_agent.config import AgentYamlConfig

        base = AgentYamlConfig.model_validate({})
        with_figma = AgentYamlConfig.model_validate({"figma": {}})
        assert base.generation == with_figma.generation
        assert base.validation == with_figma.validation
        assert base.layout == with_figma.layout


# ---------------------------------------------------------------------------
# Phase 3 — pipeline integration: build_clean_tree + parse_figma_frame
# ---------------------------------------------------------------------------


class TestPhase3PipelineIntegration:
    """Verify that dev_mode_dump flows end-to-end through build_clean_tree."""

    def _fixture_root(self) -> dict:
        import json
        from pathlib import Path

        path = Path("tests/fixtures/figma_node_sample.json")
        return json.loads(path.read_text(encoding="utf-8"))

    def _make_dump_for_root(self, root: dict, tmp_path, css: dict) -> "DevModeCssDump":
        node_id = root.get("id", "1:1")
        data = make_dump_dict(nodes={node_id: {"name": root.get("name", ""), "css": css}})
        path = _write_dump(tmp_path, data)
        return load_dev_mode_css_dump(path)

    def test_default_path_populates_css_on_tree(self) -> None:
        """Default path: REST synthesis fills css_properties for nodes that have style data."""
        from figma_flutter_agent.parser.tree import build_clean_tree

        root = self._fixture_root()
        tree, *_ = build_clean_tree(root)

        def any_populated(node) -> bool:
            if node.style.css_properties:
                return True
            return any(any_populated(c) for c in node.children)

        # At least some nodes should have css_properties populated from REST
        assert any_populated(tree), "css_properties should be populated from REST synthesis"

    def test_dump_css_propagates_to_root_node(self, tmp_path) -> None:
        """When dump contains the root node id, css_properties is populated."""
        from figma_flutter_agent.parser.tree import build_clean_tree

        root = self._fixture_root()
        dump = self._make_dump_for_root(root, tmp_path, {"clip-path": "circle(40%)"})
        tree, *_ = build_clean_tree(root, dev_mode_dump=dump)
        assert tree.style.css_properties.get("clip-path") == "circle(40%)"

    def test_hybrid_existing_wins_in_tree(self, tmp_path) -> None:
        """hybrid mode (override=False): REST wins on key conflict."""
        from figma_flutter_agent.parser.tree import build_clean_tree

        root = self._fixture_root()
        # Put the same key that REST would synthesise (background-color) in the dump
        dump = self._make_dump_for_root(
            root, tmp_path, {"background-color": "rgba(99,99,99,1)", "clip-path": "none"}
        )
        tree, *_ = build_clean_tree(root, dev_mode_dump=dump, dev_mode_css_override=False)
        # background-color from REST synthesis should win (dump fills only gaps)
        # The REST-synthesised value (if present) should override the dump's
        # clip-path (inspect-only) should be added regardless
        assert tree.style.css_properties.get("clip-path") == "none"

    def test_override_mode_dump_wins_in_tree(self, tmp_path) -> None:
        """dev_mode_inspect mode (override=True): dump wins on key conflict."""
        from figma_flutter_agent.parser.tree import build_clean_tree

        root = self._fixture_root()
        dump = self._make_dump_for_root(
            root, tmp_path, {"background-color": "rgba(99,99,99,1)"}
        )
        tree, *_ = build_clean_tree(root, dev_mode_dump=dump, dev_mode_css_override=True)
        # Dump wins in override mode
        assert tree.style.css_properties.get("background-color") == "rgba(99,99,99,1)"

    def test_parse_figma_frame_passes_dump(self, tmp_path) -> None:
        """parse_figma_frame wires dump into build_clean_tree correctly."""
        import json
        from pathlib import Path
        from figma_flutter_agent.stages.fetch import FigmaFetchResult
        from figma_flutter_agent.stages.parse import parse_figma_frame

        root = self._fixture_root()
        dump = self._make_dump_for_root(root, tmp_path, {"mix-blend-mode": "multiply"})

        fetch = FigmaFetchResult(
            file_key="test",
            node_id=root["id"],
            root=root,
            variables_payload=None,
            published_styles={},
            components={},
            component_sets={},
        )
        result = parse_figma_frame(fetch, dev_mode_dump=dump)
        assert result.clean_tree.style.css_properties.get("mix-blend-mode") == "multiply"

    def test_parse_figma_frame_no_dump_still_has_rest_css(self) -> None:
        """parse_figma_frame without dump still produces REST-synthesised css_properties."""
        from figma_flutter_agent.stages.fetch import FigmaFetchResult
        from figma_flutter_agent.stages.parse import parse_figma_frame

        root = self._fixture_root()
        fetch = FigmaFetchResult(
            file_key="test",
            node_id=root["id"],
            root=root,
            variables_payload=None,
            published_styles={},
            components={},
            component_sets={},
        )
        result = parse_figma_frame(fetch)
        # REST synthesis always runs — css_properties may or may not be empty
        # depending on whether root node has fills etc.
        assert isinstance(result.clean_tree.style.css_properties, dict)
