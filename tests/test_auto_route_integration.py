import shutil
from pathlib import Path

import pytest

from figma_flutter_agent.generator.codegen import run_build_runner, run_pub_get
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.generator.dart.project_validation import validate_dart_project
from figma_flutter_agent.generator.writer import DartWriter
from figma_flutter_agent.parser.navigation import build_feature_routes
from figma_flutter_agent.schemas import DesignTokens, FlutterGenerationResponse

_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "flutter_skeleton"
_ONBOARDING_SCREEN = """
class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(
      child: Semantics(label: 'Continue', child: const Text('Continue')),
    );
  }
}
"""
_DETAILS_SCREEN = """
class DetailsScreen extends StatelessWidget {
  const DetailsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return GeneratedScreenShell(child: const Text('Details'));
  }
}
"""


@pytest.mark.skipif(shutil.which("dart") is None, reason="dart SDK not installed")
def test_auto_route_project_passes_analyze_after_build_runner(tmp_path: Path) -> None:
    if shutil.which("flutter") is None:
        pytest.skip("flutter SDK not installed")

    project_dir = tmp_path / "project"
    shutil.copytree(_FIXTURE_ROOT, project_dir)

    renderer = DartRenderer()
    tokens = DesignTokens()
    routes = build_feature_routes("onboarding")
    routes.append(build_feature_routes("details_screen")[0])

    planned_files: dict[str, str] = {}
    planned_files.update(renderer.render_theme_files(tokens, max_web_width=480))
    planned_files.update(
        renderer.render_generation_files(
            FlutterGenerationResponse(screen_code=_ONBOARDING_SCREEN),
            feature_name="onboarding",
            use_auto_route=True,
            responsive_enabled=True,
            max_web_width=480,
        )
    )
    planned_files.update(
        renderer.render_generation_files(
            FlutterGenerationResponse(screen_code=_DETAILS_SCREEN),
            feature_name="details_screen",
            use_auto_route=True,
            responsive_enabled=True,
            max_web_width=480,
        )
    )
    planned_files.update(renderer.render_router_files(routes, "auto_route"))

    writer = DartWriter(project_dir, enable_backup=False)
    batch = writer.write_files(planned_files)
    pubspec_batch = update_pubspec(project_dir, ["assets/icons/"], needs_auto_route=True)
    run_pub_get(project_dir)
    run_build_runner(project_dir)
    validate_dart_project(project_dir)
    writer.commit_batch(batch)
    commit_pubspec_batch(pubspec_batch)

    generated_router = project_dir / "lib" / "core" / "app_router.gr.dart"
    assert generated_router.is_file()
    assert "@AutoRouterConfig" in (project_dir / "lib" / "core" / "app_router.dart").read_text(
        encoding="utf-8"
    )
