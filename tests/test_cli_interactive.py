"""Tests for interactive CLI helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import click
from typer.testing import CliRunner

from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry
from figma_flutter_agent.cli import app
from figma_flutter_agent.cli_interactive import (
    CliSession,
    WizardState,
    _menu_command,
    _wizard_menu_options,
    _wizard_resolve_screen,
    prompt_choice,
    prompt_figma_input,
    prompt_project_dir,
    prompt_screen_name,
    should_prompt,
    tty_interactive_default,
)
from figma_flutter_agent.figma.url import FigmaUrlKind

runner = CliRunner()


def _ctx(session: CliSession, *, wizard: WizardState | None = None) -> click.Context:
    ctx = click.Context(click.Command("test"))
    ctx.ensure_object(dict)
    ctx.obj["session"] = session
    if wizard is not None:
        ctx.obj["wizard"] = wizard
    return ctx


def test_should_prompt_only_when_interactive_and_value_missing() -> None:
    ctx = _ctx(CliSession(interactive=True))
    assert should_prompt(ctx, None) is True
    assert should_prompt(ctx, "sign_in") is False

    ctx = _ctx(CliSession(interactive=False))
    assert should_prompt(ctx, None) is False


def test_prompt_choice_picks_by_number() -> None:
    with patch("figma_flutter_agent.cli_interactive.typer.prompt", return_value="2"):
        assert prompt_choice("Pick", ["a", "b", "c"]) == "b"


def test_prompt_choice_zero_indexed_picks_launch_by_default() -> None:
    options = _wizard_menu_options()
    with patch("figma_flutter_agent.cli_interactive.typer.prompt", return_value="0"):
        assert prompt_choice("Pick", options, zero_indexed=True) == options[0]
    assert _menu_command(options[0]) == "launch"
    with patch("figma_flutter_agent.cli_interactive.typer.prompt", return_value="1"):
        assert prompt_choice("Pick", options, zero_indexed=True) == options[1]
    assert _menu_command(options[1]) == "switch"


def test_prompt_screen_name() -> None:
    manifest = BatchManifest(
        file_key="k",
        project_dir=Path("/p"),
        screens=(
            ScreenEntry(feature="sign_in", node_id="1:1"),
            ScreenEntry(feature="home", node_id="1:2"),
        ),
    )
    ctx = _ctx(CliSession(interactive=True))
    with patch("figma_flutter_agent.cli_interactive.typer.prompt", return_value="1"):
        assert prompt_screen_name(ctx, manifest) == "sign_in"


def test_wizard_resolve_screen_without_prompts_uses_active() -> None:
    manifest = BatchManifest(
        file_key="k",
        project_dir=Path("/p"),
        screens=(
            ScreenEntry(feature="sign_in", node_id="1:1"),
            ScreenEntry(feature="home", node_id="1:2"),
        ),
    )
    ctx = _ctx(
        CliSession(interactive=True),
        wizard=WizardState(active_screen="sign_in"),
    )
    with patch("figma_flutter_agent.cli_interactive.prompt_confirm") as confirm:
        assert _wizard_resolve_screen(ctx, manifest, without_prompts=True) == "sign_in"
        confirm.assert_not_called()


def test_wizard_resolve_screen_without_prompts_single_screen() -> None:
    manifest = BatchManifest(
        file_key="k",
        project_dir=Path("/p"),
        screens=(ScreenEntry(feature="sign_in", node_id="1:1"),),
    )
    ctx = _ctx(CliSession(interactive=True), wizard=WizardState())
    assert _wizard_resolve_screen(ctx, manifest, without_prompts=True) == "sign_in"


def test_main_shows_help_when_not_tty() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "generate" in result.stdout


def test_tty_interactive_default_false_in_runner() -> None:
    assert tty_interactive_default() is False


def test_prompt_project_dir_prompts_when_ctx_has_interactive_session(tmp_path: Path) -> None:
    flutter_root = tmp_path / "demo_app"
    flutter_root.mkdir()
    (flutter_root / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")

    ctx = _ctx(CliSession(interactive=True))
    with (
        patch(
            "figma_flutter_agent.dev.project.default_flutter_project_candidate",
            return_value=tmp_path / "missing",
        ),
        patch(
            "figma_flutter_agent.cli_interactive.typer.prompt",
            return_value=str(flutter_root),
        ),
    ):
        assert prompt_project_dir(ctx, Path(".")) == flutter_root.resolve()


def test_wizard_pick_screen_remembers_active(tmp_path: Path) -> None:
    from figma_flutter_agent.cli_interactive import WizardState, _wizard_pick_screen, _wizard_state
    from figma_flutter_agent.dev.wizard_prefs import load_wizard_prefs

    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    manifest = BatchManifest(
        file_key="k",
        project_dir=project_dir,
        screens=(
            ScreenEntry(feature="sign_in", node_id="1:1"),
            ScreenEntry(feature="home", node_id="1:2"),
        ),
    )
    ctx = _ctx(CliSession(interactive=True))
    state = WizardState(project_dir=project_dir, active_screen="sign_in")
    ctx.obj["wizard"] = state
    with patch("figma_flutter_agent.cli_interactive.typer.prompt", return_value="2"):
        picked = _wizard_pick_screen(ctx, manifest)
    assert picked == "home"
    assert _wizard_state(ctx).active_screen == "home"
    assert load_wizard_prefs(project_dir).active_screen == "home"


def test_bootstrap_wizard_state_loads_persisted_screen(tmp_path: Path, monkeypatch) -> None:
    from figma_flutter_agent.cli_interactive import (
        WizardState,
        _bootstrap_wizard_state,
        _wizard_state,
    )
    from figma_flutter_agent.dev.wizard_prefs import save_wizard_prefs

    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    save_wizard_prefs(project_dir, active_screen="music_v2")
    monkeypatch.setenv("FIGMA_FLUTTER_PROJECT_DIR", str(project_dir))
    monkeypatch.setenv("FIGMA_SMOKE_FILE_KEY", "some_file_key")

    ctx = _ctx(CliSession(interactive=True))
    ctx.obj["wizard"] = WizardState()
    _bootstrap_wizard_state(ctx)
    state = _wizard_state(ctx)
    assert state.project_dir == project_dir.resolve()
    assert state.active_screen == "music_v2"


def test_prompt_figma_input_optional_skips_without_default() -> None:
    with patch("figma_flutter_agent.cli_interactive.typer.prompt", return_value=""):
        assert prompt_figma_input(optional=True) is None


def test_prompt_figma_input_uses_manifest_default(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    manifest_path = project_dir / "screens.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "file_key: abc123",
                "project_dir: .",
                "screens:",
                "  - feature: sign_in",
                "    node_id: 1:100",
                "    figma_url: https://www.figma.com/design/abc123/App?node-id=1-100",
            ]
        ),
        encoding="utf-8",
    )
    frame_url = "https://www.figma.com/design/abc123/App?node-id=1-100"
    with patch(
        "figma_flutter_agent.cli_interactive.typer.prompt",
        return_value=frame_url,
    ) as prompt:
        parsed = prompt_figma_input(
            expect_kind=FigmaUrlKind.FRAME,
            project_dir=project_dir,
        )
    assert "node-id=1-100" in prompt.call_args.kwargs["default"]
    assert parsed is not None
    assert parsed.node_id == "1:100"


def test_wizard_check_skips_fonts_until_fonts_submenu() -> None:
    from figma_flutter_agent.cli_interactive import _wizard_check

    ctx = _ctx(CliSession(interactive=True))
    with (
        patch(
            "figma_flutter_agent.cli_interactive.prompt_choice",
            return_value="doctor — Figma token, Flutter SDK, project files",
        ),
        patch(
            "figma_flutter_agent.cli_interactive._wizard_print_font_audit",
        ) as font_audit,
        patch("figma_flutter_agent.cli_interactive._wizard_doctor"),
    ):
        _wizard_check(ctx)
    font_audit.assert_not_called()


def test_wizard_check_runs_fonts_on_fonts_submenu() -> None:
    from figma_flutter_agent.cli_interactive import _wizard_check

    ctx = _ctx(CliSession(interactive=True))
    with (
        patch(
            "figma_flutter_agent.cli_interactive.prompt_choice",
            return_value="fonts — audit assets/fonts/ and active screen dump",
        ),
        patch(
            "figma_flutter_agent.cli_interactive._wizard_print_font_audit",
            return_value=True,
        ) as font_audit,
    ):
        _wizard_check(ctx)
    font_audit.assert_called_once()


def test_run_requires_screen_when_non_interactive() -> None:
    tmp = Path(__file__).resolve().parents[1]
    demo = tmp / "demo_app_probe"
    if not (demo / "pubspec.yaml").is_file():
        demo = Path("E:/@dev/demo_app")
    if not (demo / "pubspec.yaml").is_file() or not (demo / "screens.yaml").is_file():
        return
    result = runner.invoke(
        app,
        ["--no-interactive", "run", "--project-dir", str(demo)],
    )
    assert result.exit_code == 1
    assert "Screen name required" in result.stdout
