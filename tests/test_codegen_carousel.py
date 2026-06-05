"""Codegen validation must accept deterministic carousel layouts."""

import json
from pathlib import Path

from figma_flutter_agent.generator.codegen_checks import validate_generated_dart
from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.parser.tree import build_clean_tree


def test_carousel_layout_passes_validate_generated_dart() -> None:
    root = json.loads(Path("tests/fixtures/figma_carousel_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)
    layout_files = render_layout_file(tree, feature_name="hero", uses_svg=False)
    screen_files = {
        "lib/features/hero/hero_screen.dart": """
import 'package:flutter/material.dart';
import 'package:demo_app/generated/hero_layout.dart';

class HeroScreen extends StatelessWidget {
  const HeroScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return const GeneratedScreenShell(child: HeroLayout());
  }
}
""",
    }

    validate_generated_dart(
        {**layout_files, **screen_files},
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=True,
    )
