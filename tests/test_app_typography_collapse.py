from figma_flutter_agent.generator.app_typography_collapse import (
    collapse_inline_text_styles_to_app_typography,
)
from figma_flutter_agent.schemas import DesignTokens, TypographyStyle


def test_collapse_theme_copy_with_to_app_typography() -> None:
    tokens = DesignTokens(
        typography={
            "button_label": TypographyStyle(fontSize=14.0, fontWeight="w700"),
        }
    )
    source = """
import 'package:flutter/material.dart';

Widget build(BuildContext context) {
  return Text(
    'CONTINUE WITH GOOGLE',
    style: Theme.of(context).textTheme.titleMedium?.copyWith(
      color: Color(0xFF3F414E),
      fontSize: 14.0,
      fontWeight: FontWeight.w700,
    ),
  );
}
"""
    updated = collapse_inline_text_styles_to_app_typography(
        source,
        tokens,
        package_name="demo_app",
    )
    assert "AppTypography.button_label" in updated
    assert "fontSize: 14.0" not in updated
    assert "app_typography.dart" in updated
