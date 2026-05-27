from pathlib import Path

import pytest

from figma_flutter_agent.errors import FigmaUrlError
from figma_flutter_agent.figma.url import (
    FigmaUrlKind,
    describe_figma_input,
    parse_figma_input,
    parse_figma_url,
    resolve_default_figma_input,
    resolve_smoke_frame,
)


def test_parse_design_url() -> None:
    parsed = parse_figma_url("https://www.figma.com/design/AbCdEf/Test?node-id=123-456")
    assert parsed.file_key == "AbCdEf"
    assert parsed.node_id == "123:456"


def test_parse_url_requires_node_id() -> None:
    with pytest.raises(FigmaUrlError, match="node-id"):
        parse_figma_url("https://www.figma.com/design/AbCdEf/Test")


def test_parse_url_rejects_invalid_node_id() -> None:
    with pytest.raises(FigmaUrlError, match="Invalid node id"):
        parse_figma_url("https://www.figma.com/design/AbCdEf/Test?node-id=123")


def test_parse_url_rejects_missing_file_key() -> None:
    with pytest.raises(FigmaUrlError, match="file key"):
        parse_figma_url("https://example.com/?node-id=123-456")


def test_resolve_smoke_frame_prefers_figma_url() -> None:
    file_key, node_id = resolve_smoke_frame(
        figma_url="https://www.figma.com/design/FromUrl/n?node-id=10-20",
        file_key="env-key",
        node_id="99:99",
    )
    assert file_key == "FromUrl"
    assert node_id == "10:20"


def test_resolve_smoke_frame_uses_env_when_no_url() -> None:
    file_key, node_id = resolve_smoke_frame(
        figma_url=None,
        file_key=" env-key ",
        node_id=" 1:2 ",
    )
    assert file_key == "env-key"
    assert node_id == "1:2"


def test_parse_figma_input_frame_url() -> None:
    parsed = parse_figma_input("https://www.figma.com/design/AbCdEf/Test?node-id=123-456")
    assert parsed.kind == FigmaUrlKind.FRAME
    assert parsed.file_key == "AbCdEf"
    assert parsed.node_id == "123:456"
    assert parsed.is_frame
    assert not parsed.is_file


def test_parse_figma_input_file_url() -> None:
    parsed = parse_figma_input("https://www.figma.com/design/AbCdEf/Test")
    assert parsed.kind == FigmaUrlKind.FILE
    assert parsed.file_key == "AbCdEf"
    assert parsed.node_id is None
    assert parsed.is_file


def test_parse_figma_input_bare_file_key() -> None:
    parsed = parse_figma_input("AbCdEf")
    assert parsed.kind == FigmaUrlKind.FILE
    assert parsed.file_key == "AbCdEf"


def test_parse_figma_input_rejects_empty() -> None:
    with pytest.raises(FigmaUrlError, match="empty"):
        parse_figma_input("   ")


def test_describe_figma_input() -> None:
    frame = parse_figma_input("https://www.figma.com/design/AbCdEf/Test?node-id=1-2")
    assert "single frame 1:2" in describe_figma_input(frame)
    file_only = parse_figma_input("AbCdEf")
    assert describe_figma_input(file_only) == "full Figma file AbCdEf"


def test_resolve_default_figma_input_prefers_manifest_file_url() -> None:
    from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry

    manifest = BatchManifest(
        file_key="abc123",
        project_dir=Path("/demo"),
        figma_file_url="https://www.figma.com/design/abc123/App",
        screens=(ScreenEntry(feature="sign_in", node_id="1:1"),),
    )
    default = resolve_default_figma_input(
        prefer_kind=FigmaUrlKind.FILE,
        manifest=manifest,
        figma_default_url="https://www.figma.com/design/other/File",
    )
    assert default == "https://www.figma.com/design/abc123/App"


def test_resolve_default_figma_input_active_screen_frame() -> None:
    from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry

    manifest = BatchManifest(
        file_key="abc123",
        project_dir=Path("/demo"),
        screens=(
            ScreenEntry(
                feature="music_v2",
                node_id="1:3978",
                figma_url="https://www.figma.com/design/abc123/App?node-id=1-3978",
            ),
        ),
    )
    default = resolve_default_figma_input(
        prefer_kind=FigmaUrlKind.FRAME,
        manifest=manifest,
        active_screen="music_v2",
    )
    assert default.endswith("node-id=1-3978")


def test_resolve_default_figma_input_env_smoke_fallback() -> None:
    default = resolve_default_figma_input(
        prefer_kind=FigmaUrlKind.FRAME,
        figma_smoke_file_key="smokeKey",
        figma_smoke_node_id="1:2",
    )
    assert "smokeKey" in default
    assert "node-id=1-2" in default


def test_resolve_default_figma_input_env_default_url() -> None:
    default = resolve_default_figma_input(
        figma_default_url="https://www.figma.com/design/fromEnv/App?node-id=9-9",
    )
    assert "fromEnv" in default
