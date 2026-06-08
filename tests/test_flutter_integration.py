import shutil
from pathlib import Path

import pytest

from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.generator.dart.project_validation import validate_dart_project
from figma_flutter_agent.generator.writing.core import DartWriter
from figma_flutter_agent.schemas import DesignTokens, ExtractedWidget, FlutterGenerationResponse

_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "flutter_skeleton"
_VALID_SCREEN = """
class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(
      child: Semantics(
        label: 'Continue',
        child: const PrimaryButton(),
      ),
    );
  }
}
"""
_VALID_WIDGET = """
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.all(AppSpacing.medium),
      child: SvgPicture.asset('assets/icons/placeholder.svg'),
    );
  }
}
"""


@pytest.mark.skipif(shutil.which("dart") is None, reason="dart SDK not installed")
def test_generated_project_passes_flutter_analyze(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    shutil.copytree(_FIXTURE_ROOT, project_dir)

    tokens = DesignTokens()
    renderer = DartRenderer()
    response = FlutterGenerationResponse(
        screen_code=_VALID_SCREEN,
        extracted_widgets=[
            ExtractedWidget(widget_name="PrimaryButton", code=_VALID_WIDGET),
        ],
    )

    planned_files: dict[str, str] = {}
    planned_files.update(renderer.render_theme_files(tokens))
    planned_files.update(
        renderer.render_generation_files(
            response,
            feature_name="onboarding",
            uses_svg=True,
            responsive_enabled=True,
            max_web_width=480,
        )
    )
    planned_files.update(
        renderer.render_app_bootstrap(
            feature_name="onboarding",
            screen_class="OnboardingScreen",
            app_title="Onboarding",
            routing_type="none",
            routing_enabled=False,
            generate_dark_mode=False,
            max_web_width=480,
        )
    )

    writer = DartWriter(project_dir, enable_backup=False)
    batch = writer.write_files(planned_files)
    pubspec_batch = update_pubspec(project_dir, ["assets/icons/"], needs_svg=True)
    validate_dart_project(project_dir)
    writer.commit_batch(batch)
    commit_pubspec_batch(pubspec_batch)
