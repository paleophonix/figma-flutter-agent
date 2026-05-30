from pathlib import Path

from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.schemas import ExtractedWidget, FlutterGenerationResponse


def test_render_generation_files_imports_extracted_widgets_in_screen() -> None:
    renderer = DartRenderer()
    response = FlutterGenerationResponse(
        screen_code="class OnboardingScreen extends StatelessWidget { const OnboardingScreen({super.key}); @override Widget build(BuildContext c) => const PrimaryButton(); }",
        extracted_widgets=[
            ExtractedWidget(
                widget_name="PrimaryButton",
                code="class PrimaryButton extends StatelessWidget { const PrimaryButton({super.key}); @override Widget build(BuildContext c) => Padding(padding: EdgeInsets.all(AppSpacing.medium), child: const Text('Go')); }",
            )
        ],
    )

    files = renderer.render_generation_files(response, feature_name="onboarding", uses_svg=True)

    screen = files["lib/features/onboarding/onboarding_screen.dart"]
    widget = files["lib/widgets/primary_button.dart"]

    assert "import 'package:demo_app/widgets/primary_button.dart';" in screen
    assert "import 'package:flutter_svg/flutter_svg.dart';" in screen
    assert "import 'package:demo_app/theme/app_spacing.dart';" in screen
    assert "import 'package:demo_app/theme/app_colors.dart';" in screen
    assert "import 'package:demo_app/theme/app_spacing.dart';" in widget
    assert "import 'package:demo_app/theme/app_colors.dart';" in widget
    assert "import 'package:flutter_svg/flutter_svg.dart';" in widget


def test_render_generation_files_reconciles_private_extracted_widgets() -> None:
    renderer = DartRenderer()
    response = FlutterGenerationResponse(
        screen_code="""class MusicV2Screen extends StatelessWidget {
  const MusicV2Screen({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      _CircleAction(icon: Icons.share),
    ]);
  }
}""",
        extracted_widgets=[
            ExtractedWidget(
                widget_name="CircleAction",
                code="""class _CircleAction extends StatelessWidget {
  const _CircleAction({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Icon(icon);
  }
}""",
            )
        ],
    )

    files = renderer.render_generation_files(response, feature_name="music_v2")
    screen = files["lib/features/music_v2/music_v2_screen.dart"]
    widget = files["lib/widgets/circle_action.dart"]

    assert "CircleAction(icon: Icons.share)" in screen
    assert "_CircleAction(" not in screen
    assert "class CircleAction extends StatelessWidget" in widget
    assert "import 'package:demo_app/widgets/circle_action.dart';" in screen


def test_render_generation_files_adds_sibling_imports_between_extracted_widgets() -> None:
    renderer = DartRenderer()
    response = FlutterGenerationResponse(
        screen_code="""class MusicV2Screen extends StatelessWidget {
  const MusicV2Screen({super.key});

  @override
  Widget build(BuildContext context) {
    return const PlayerControls();
  }
}""",
        extracted_widgets=[
            ExtractedWidget(
                widget_name="ControlCircleIcon",
                code="""class _ControlCircleIcon extends StatelessWidget {
  const _ControlCircleIcon({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Icon(icon);
  }
}
""",
            ),
            ExtractedWidget(
                widget_name="PlayerControls",
                code="""class PlayerControls extends StatelessWidget {
  const PlayerControls({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      ControlCircleIcon(icon: Icons.share),
    ]);
  }
}
""",
            ),
        ],
    )

    files = renderer.render_generation_files(response, feature_name="music_v2")
    player = files["lib/widgets/player_controls.dart"]
    control = files["lib/widgets/control_circle_icon.dart"]

    assert "import 'package:demo_app/widgets/control_circle_icon.dart';" in player
    assert "ControlCircleIcon(icon: Icons.share)" in player
    assert "class ControlCircleIcon extends StatelessWidget" in control


def test_render_app_bootstrap_standalone_uses_material_app_home() -> None:
    files = DartRenderer().render_app_bootstrap(
        feature_name="onboarding",
        screen_class="OnboardingScreen",
        app_title="Onboarding",
        routing_type="none",
        routing_enabled=False,
        generate_dark_mode=True,
        max_web_width=480,
    )

    content = files["lib/main.dart"]
    assert "void main()" in content
    assert "home: const OnboardingScreen()" in content
    assert "ThemeMode.system" in content
    assert "package:demo_app/features/onboarding/onboarding_screen.dart" in content
    assert "package:demo_app/theme/app_theme.dart" in content


def test_render_app_bootstrap_go_router_uses_router_config() -> None:
    files = DartRenderer().render_app_bootstrap(
        feature_name="onboarding",
        screen_class="OnboardingScreen",
        app_title="Onboarding",
        routing_type="go_router",
        routing_enabled=True,
        generate_dark_mode=False,
        max_web_width=560,
    )

    content = files["lib/main.dart"]
    assert "MaterialApp.router" in content
    assert "routerConfig: AppRouter.router" in content
    assert "package:demo_app/core/app_router.dart" in content


def test_render_app_bootstrap_riverpod_wraps_provider_scope() -> None:
    files = DartRenderer().render_app_bootstrap(
        feature_name="onboarding",
        screen_class="OnboardingScreen",
        app_title="Onboarding",
        routing_type="none",
        routing_enabled=False,
        generate_dark_mode=False,
        max_web_width=480,
        state_management_type="riverpod",
    )

    content = files["lib/main.dart"]
    assert "package:flutter_riverpod/flutter_riverpod.dart" in content
    assert "ProviderScope(child: FigmaFlutterApp())" in content


def test_render_app_bootstrap_bloc_wraps_bloc_provider() -> None:
    files = DartRenderer().render_app_bootstrap(
        feature_name="onboarding",
        screen_class="OnboardingScreen",
        app_title="Onboarding",
        routing_type="none",
        routing_enabled=False,
        generate_dark_mode=False,
        max_web_width=480,
        state_management_type="bloc",
    )

    content = files["lib/main.dart"]
    assert "package:flutter_bloc/flutter_bloc.dart" in content
    assert "BlocProvider(" in content
    assert "OnboardingScreenCubit()" in content
    assert "package:demo_app/features/onboarding/onboarding_state.dart" in content


def test_render_generation_files_bloc_wraps_screen_with_bloc_builder() -> None:
    renderer = DartRenderer()
    response = FlutterGenerationResponse(
        screen_code="""class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return const Text('Hello');
  }
}"""
    )

    files = renderer.render_generation_files(
        response,
        feature_name="onboarding",
        state_management_type="bloc",
    )

    screen = files["lib/features/onboarding/onboarding_screen.dart"]
    assert "BlocBuilder<OnboardingScreenCubit, OnboardingScreenState>" in screen
    assert "package:flutter_bloc/flutter_bloc.dart" in screen


def test_render_app_bootstrap_cupertino_uses_cupertino_app() -> None:
    files = DartRenderer().render_app_bootstrap(
        feature_name="onboarding",
        screen_class="OnboardingScreen",
        app_title="Onboarding",
        routing_type="none",
        routing_enabled=False,
        generate_dark_mode=False,
        max_web_width=480,
        theme_variant="cupertino",
    )

    content = files["lib/main.dart"]
    assert "CupertinoApp(" in content
    assert "AppCupertinoTheme.light" in content
    assert "package:demo_app/theme/app_cupertino_theme.dart" in content


def test_render_golden_test_emits_widget_golden_scaffold() -> None:
    files = DartRenderer().render_golden_test(
        feature_name="onboarding",
        screen_class="OnboardingScreen",
        package_name="demo_app",
        surface_width=360,
        surface_height=640,
        max_web_width=480,
    )

    content = files["test/golden/onboarding_screen_test.dart"]
    assert "matchesGoldenFile('../goldens/onboarding_screen.png')" in content
    assert "package:demo_app/features/onboarding/onboarding_screen.dart" in content
    assert "setSurfaceSize(" in content
    assert "const Size(360, 640)" in content
    assert "await tester.pump();" in content
    assert "pump(const Duration(milliseconds: 400))" in content
    assert "pump(const Duration(milliseconds: 500))" in content
    assert "timeout: const Timeout" not in content
    assert "test/harness/element_coordinate_mapper.dart" in files
    assert "class ElementCoordinateMapper" in files["test/harness/element_coordinate_mapper.dart"]


def test_golden_harness_matches_skeleton_fixture() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    packaged = (
        repo_root
        / "src/figma_flutter_agent/generator/templates/element_coordinate_mapper.harness"
    )
    fixture = (
        repo_root
        / "tests/fixtures/flutter_skeleton/test/harness/element_coordinate_mapper.dart"
    )
    assert packaged.read_text(encoding="utf-8") == fixture.read_text(encoding="utf-8")
