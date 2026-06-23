"""Tests for FFA_RUN_ID stamp in debug Dart bundles."""

from __future__ import annotations

from figma_flutter_agent.debug.dart_bundle import build_planned_dart_bundle


def test_build_planned_dart_bundle_stamps_run_id() -> None:
    planned = {
        "lib/features/login/login_screen.dart": (
            "import 'package:demo_app/widgets/foo.dart';\n"
            "class LoginScreen extends StatelessWidget { const LoginScreen({super.key}); "
            "@override Widget build(BuildContext context) => const SizedBox(); }\n"
        ),
    }
    bundle = build_planned_dart_bundle(
        feature_name="login",
        planned_files=planned,
        package_name="demo_app",
        pipeline_run_id="run_stamp_123",
    )
    assert bundle is not None
    assert "// FFA_RUN_ID: run_stamp_123" in bundle
