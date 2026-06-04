"""Tests for debug Dart bundle assembly."""

from __future__ import annotations

from figma_flutter_agent.debug.dart_bundle import (
    build_dart_debug_bundle,
    detect_screen_class_from_planned_files,
    parse_planned_dart_bundle,
    planned_files_from_dart_bundle,
    write_dart_debug_bundle,
)


def test_build_dart_debug_bundle_inlines_widgets_and_layout() -> None:
    planned = {
        "lib/widgets/logo.dart": """
import 'package:demo_app/theme/app_colors.dart';

class Logo extends StatelessWidget {
  const Logo({super.key});
  @override
  Widget build(BuildContext context) => const Text('Logo');
}
""",
        "lib/generated/sign_in_layout.dart": """
import 'package:demo_app/widgets/logo.dart';

class SignInLayout extends StatelessWidget {
  const SignInLayout({super.key});
  @override
  Widget build(BuildContext context) => const Logo();
}
""",
        "lib/features/sign_in/sign_in_screen.dart": """
import 'package:flutter/material.dart';
import 'package:demo_app/generated/sign_in_layout.dart';

class SignInScreen extends StatelessWidget {
  const SignInScreen({super.key});
  @override
  Widget build(BuildContext context) => const SignInLayout();
}
""",
    }
    bundle = build_dart_debug_bundle(
        feature_name="sign_in",
        planned_files=planned,
        package_name="demo_app",
    )
    assert bundle is not None
    assert "import 'package:demo_app/widgets/logo.dart';" not in bundle
    assert "import 'package:demo_app/generated/sign_in_layout.dart';" not in bundle
    assert "import 'package:flutter/material.dart';" in bundle
    assert "// --- begin lib/widgets/logo.dart ---" in bundle
    assert "// --- begin lib/generated/sign_in_layout.dart ---" in bundle
    assert "// --- begin lib/features/sign_in/sign_in_screen.dart ---" in bundle
    assert bundle.index("class Logo") < bundle.index("class SignInLayout")
    assert bundle.index("class SignInLayout") < bundle.index("class SignInScreen")


def test_write_dart_debug_bundle(tmp_path) -> None:
    planned = {
        "lib/features/home/home_screen.dart": """
import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}
""",
    }
    path = write_dart_debug_bundle(
        tmp_path,
        feature_name="home",
        planned_files=planned,
        package_name="demo_app",
    )
    assert path is not None
    assert path.name == "home_screen.dart"
    assert path.parent.name == "dart"
    assert "class HomeScreen" in path.read_text(encoding="utf-8")


def test_detect_screen_class_skips_generated_screen_shell() -> None:
    planned = {
        "lib/features/background/background_screen.dart": """
class GeneratedScreenShell extends StatelessWidget {
  const GeneratedScreenShell({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => child;
}

class BackgroundScreen extends StatelessWidget {
  const BackgroundScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return GeneratedScreenShell(child: const BackgroundLayout());
  }
}
""",
    }
    assert (
        detect_screen_class_from_planned_files(planned, feature_name="background")
        == "BackgroundScreen"
    )


def test_planned_files_from_dart_bundle_roundtrip() -> None:
    planned = {
        "lib/widgets/logo.dart": """
import 'package:flutter/material.dart';

class Logo extends StatelessWidget {
  const Logo({super.key});
  @override
  Widget build(BuildContext context) => const Text('Logo');
}
""",
        "lib/generated/sign_in_layout.dart": """
import 'package:demo_app/widgets/logo.dart';

class SignInLayout extends StatelessWidget {
  const SignInLayout({super.key});
  @override
  Widget build(BuildContext context) => const Logo();
}
""",
        "lib/features/sign_in/sign_in_screen.dart": """
import 'package:flutter/material.dart';
import 'package:demo_app/generated/sign_in_layout.dart';

class SignInScreen extends StatelessWidget {
  const SignInScreen({super.key});
  @override
  Widget build(BuildContext context) => const SignInLayout();
}
""",
    }
    bundle = build_dart_debug_bundle(
        feature_name="sign_in",
        planned_files=planned,
        package_name="demo_app",
    )
    assert bundle is not None
    external, sections = parse_planned_dart_bundle(bundle)
    assert "import 'package:flutter/material.dart';" in external
    assert set(sections) == set(planned)

    restored = planned_files_from_dart_bundle(bundle, package_name="demo_app")
    assert "class SignInScreen" in restored["lib/features/sign_in/sign_in_screen.dart"]
    assert "import 'package:demo_app/generated/sign_in_layout.dart';" in restored[
        "lib/features/sign_in/sign_in_screen.dart"
    ]
    assert "class SignInLayout" in restored["lib/generated/sign_in_layout.dart"]
    assert "import 'package:demo_app/widgets/logo.dart';" in restored[
        "lib/generated/sign_in_layout.dart"
    ]
