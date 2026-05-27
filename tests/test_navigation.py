from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.llm.prompts import build_system_prompt
from figma_flutter_agent.parser.navigation import build_feature_routes


def test_build_system_prompt_allows_external_router_when_enabled() -> None:
    enabled = build_system_prompt(routing_enabled=True)
    disabled = build_system_prompt(routing_enabled=False)

    assert "navigationHints" in enabled or "navigation is generated separately" in enabled
    assert "Do not generate routing" in disabled


def test_render_router_files_emits_go_router_bootstrap() -> None:
    renderer = DartRenderer()
    routes = build_feature_routes("onboarding")
    files = renderer.render_router_files(routes, "go_router")

    assert "lib/core/app_router.dart" in files
    content = files["lib/core/app_router.dart"]
    assert "package:go_router/go_router.dart" in content
    assert "OnboardingScreen" in content
    assert "// <custom-code>" in content


def test_render_router_files_supports_navigator2_backend() -> None:
    renderer = DartRenderer()
    routes = build_feature_routes("onboarding")
    files = renderer.render_router_files(routes, "navigator2")

    content = files["lib/core/app_router.dart"]
    assert "RouterDelegate" in content
    assert "// <custom-code>" in content


def test_render_router_files_generates_auto_route_stub() -> None:
    renderer = DartRenderer()
    routes = build_feature_routes("onboarding")
    files = renderer.render_router_files(routes, "auto_route")

    router = files["lib/core/app_router.dart"]
    stub = files["lib/core/app_router.gr.dart"]
    assert "@AutoRouterConfig" in router
    assert "part 'app_router.gr.dart';" in router
    assert "class OnboardingRoute extends PageRouteInfo<void>" in stub
    assert "AutoRoute(page: OnboardingRoute.page, initial: true)" in router


def test_render_generation_files_injects_responsive_shell_and_route_page() -> None:
    renderer = DartRenderer()
    from figma_flutter_agent.schemas import FlutterGenerationResponse

    files = renderer.render_generation_files(
        FlutterGenerationResponse(screen_code="class OnboardingScreen extends StatelessWidget {}"),
        feature_name="onboarding",
        use_auto_route=True,
        responsive_enabled=True,
        max_web_width=560,
        layout_import="onboarding_layout",
    )

    screen = files["lib/features/onboarding/onboarding_screen.dart"]
    assert "class GeneratedScreenShell extends StatelessWidget" in screen
    assert "LayoutBuilder" in screen
    assert "AppBreakpoints" in screen
    assert "@RoutePage()" in screen
    assert "import 'package:demo_app/generated/onboarding_layout.dart';" in screen
    assert "import 'package:demo_app/theme/app_layout.dart';" in screen
