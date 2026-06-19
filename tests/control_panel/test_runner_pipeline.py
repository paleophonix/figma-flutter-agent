"""Tests for Discord runner pipeline settings."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from control_panel.runner.pipeline import execute_generation_pipeline
from figma_flutter_agent.config import Settings


@pytest.mark.asyncio
async def test_execute_generation_pipeline_skips_production_profile_by_default(
    tmp_path: Path,
) -> None:
    """Discord jobs should match wizard: YAML settings without forced production gates."""
    settings = Settings()
    assert settings.agent.quality.strict_contrast is False

    with (
        patch(
            "control_panel.runner.pipeline.load_settings",
            return_value=settings,
        ) as load_mock,
        patch(
            "control_panel.runner.pipeline.apply_production_profile",
            side_effect=AssertionError("production profile must not run"),
        ),
        patch(
            "control_panel.runner.pipeline.run_pipeline",
            new_callable=AsyncMock,
            return_value=MagicMock(written_files=[], planned_files=[]),
        ),
        patch("control_panel.runner.pipeline.parse_figma_url"),
        patch("control_panel.runner.pipeline.infer_feature_slug", return_value="login"),
    ):
        await execute_generation_pipeline(
            figma_url="https://www.figma.com/design/abc/Name?node-id=1-2",
            project_dir=tmp_path,
            use_production_profile=False,
        )

    load_mock.assert_called_once()


@pytest.mark.asyncio
async def test_execute_generation_pipeline_applies_production_profile_when_enabled(
    tmp_path: Path,
) -> None:
    """Strict gates apply only when control-plane generation.use_production_profile is true."""
    dev_settings = Settings()
    prod_settings = dev_settings.model_copy(
        update={
            "agent": dev_settings.agent.model_copy(
                update={
                    "quality": dev_settings.agent.quality.model_copy(
                        update={"strict_contrast": True}
                    )
                }
            )
        }
    )

    with (
        patch(
            "control_panel.runner.pipeline.load_settings",
            return_value=dev_settings,
        ),
        patch(
            "control_panel.runner.pipeline.apply_production_profile",
            return_value=prod_settings,
        ) as apply_mock,
        patch(
            "control_panel.runner.pipeline.run_pipeline",
            new_callable=AsyncMock,
            return_value=MagicMock(written_files=[], planned_files=[]),
        ) as run_mock,
        patch("control_panel.runner.pipeline.parse_figma_url"),
        patch("control_panel.runner.pipeline.infer_feature_slug", return_value="login"),
    ):
        await execute_generation_pipeline(
            figma_url="https://www.figma.com/design/abc/Name?node-id=1-2",
            project_dir=tmp_path,
            use_production_profile=True,
        )

    apply_mock.assert_called_once_with(dev_settings)
    assert run_mock.await_args is not None
    passed_settings = run_mock.await_args.args[0]
    assert passed_settings.agent.quality.strict_contrast is True
