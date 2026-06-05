"""Pipeline warning policy (expected noise vs actionable hints)."""

from __future__ import annotations

from figma_flutter_agent.config import Settings, load_settings
from figma_flutter_agent.parser.dev_mode_css import DevModeCssDumpError
from figma_flutter_agent.pipeline.warning_policy import (
    cached_ir_user_warning,
    log_dev_mode_css_load_failure,
    quiet_expected_warnings,
    skip_delegates_to_layout_warning,
)


def _settings(*, quiet: bool) -> Settings:
    base = load_settings(config_path=None)
    return base.model_copy(
        update={
            "agent": base.agent.model_copy(
                update={
                    "runtime": base.agent.runtime.model_copy(
                        update={"quiet_expected_warnings": quiet}
                    )
                }
            )
        }
    )


def test_quiet_expected_default_true() -> None:
    settings = load_settings(config_path=None)
    assert quiet_expected_warnings(settings) is True


def test_cached_ir_warning_suppressed_when_quiet() -> None:
    settings = _settings(quiet=True)
    assert cached_ir_user_warning("Skipped LLM IR", settings=settings) is None


def test_cached_ir_warning_shown_when_loud() -> None:
    settings = _settings(quiet=False)
    assert cached_ir_user_warning("Skipped LLM IR", settings=settings) == "Skipped LLM IR"


def test_skip_delegates_when_cached_ir_and_quiet() -> None:
    settings = _settings(quiet=True)
    assert skip_delegates_to_layout_warning(settings=settings, use_cached_ir=True) is True


def test_dev_mode_css_hybrid_missing_is_optional() -> None:
    settings = _settings(quiet=True)

    class _Log:
        def __init__(self) -> None:
            self.info_called = False
            self.warning_called = False

        def info(self, *_args: object, **_kwargs: object) -> None:
            self.info_called = True

        def warning(self, *_args: object, **_kwargs: object) -> None:
            self.warning_called = True

    log = _Log()
    log_dev_mode_css_load_failure(
        log,
        settings=settings,
        style_source="hybrid",
        exc=DevModeCssDumpError("missing"),
    )
    assert log.info_called is True
    assert log.warning_called is False
