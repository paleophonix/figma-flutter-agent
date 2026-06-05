"""Tests for deterministic ``])))}}``-style format-parse repairs."""

from __future__ import annotations

from figma_flutter_agent.generator.app_typography_collapse import (
    collapse_inline_text_styles_to_app_typography,
)
from figma_flutter_agent.generator.dart.syntax_repairs import (
    append_missing_closers_on_lines,
    fix_elevated_button_label_on_saturated_background,
    fix_text_align_square_bracket_close,
    is_garbage_closer_only_line,
    is_orphan_semicolon_line,
    normalize_app_typography_style_references,
    parse_format_error_line_numbers,
    strip_duplicate_key_after_super,
    strip_garbage_closer_only_lines,
    strip_orphan_semicolon_only_lines,
    use_scale_down_for_design_canvas_fittedbox,
    wrap_misplaced_text_style_params_on_text,
)
from figma_flutter_agent.generator.planned_dart import (
    fallback_unparseable_screens_to_layout,
    repair_planned_format_parse_failures,
    sanitize_screen_emit_syntax,
)
from figma_flutter_agent.schemas import DesignTokens, TypographyStyle


def test_is_garbage_closer_only_line() -> None:
    assert is_garbage_closer_only_line("])))}}")
    assert is_garbage_closer_only_line("  )))  ")
    assert not is_garbage_closer_only_line("      ),")
    assert not is_garbage_closer_only_line("child: Text('x'),")


def test_strip_garbage_closer_only_lines() -> None:
    source = "Stack(\n  children: [\n    Text('x'),\n])))}}\n  ],\n)"
    fixed = strip_garbage_closer_only_lines(source)
    assert "])))}}" not in fixed
    assert "Text('x')" in fixed


def test_parse_format_error_line_numbers() -> None:
    errors = (
        "line 241, column 4 of /tmp/lib/features/sign_in/sign_in_screen.dart: Expected to find ';'.",
    )
    assert parse_format_error_line_numbers(errors) == (241,)


def test_append_missing_closers_on_lines() -> None:
    source = "return Stack(children: [Text('a'), Text('b')"
    fixed = append_missing_closers_on_lines(source, (1,))
    assert fixed.rstrip().endswith("])")


def test_sanitize_screen_emit_syntax_fixes_minified_sign_up_text() -> None:
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    source = (
        "child: Semantics(label: 'afsar', child: Text('afsar', "
        "style: Theme.of(context).textTheme.headlineLarge?.copyWith(color: Color(0xFF3F414E)), "
        "textScaler: MediaQuery.textScalerOf(context)), textScaler: MediaQuery.textScalerOf(context))), "
        "fontSize: 16.0, fontWeight: FontWeight.w300, height: 1.08, "
        "leadingDistribution: TextLeadingDistribution.proportional, letterSpacing: 0.8, "
        "textScaler: textScaler, textAlign: TextAlign.left])),"
    )
    fixed = sanitize_screen_emit_syntax(source)
    assert "copyWith(color: Color(0xFF3F414E), fontSize: 16.0" in fixed
    assert "textAlign: TextAlign.left])" not in fixed
    assert "textAlign: TextAlign.left)" in fixed
    assert fixed.count("textScaler: MediaQuery.textScalerOf(context)") == 1
    assert validate_dart_delimiters(f"void x(){{ return Stack(children: [{fixed}]); }}") is None


def test_sanitize_screen_emit_syntax_wraps_misplaced_text_style_params() -> None:
    from figma_flutter_agent.generator.planned_dart import sanitize_screen_emit_syntax

    source = (
        "child: Semantics(label: 'afsar', child: Text('afsar', "
        "style: Theme.of(context).textTheme.headlineLarge?.copyWith("
        "color: Color(0xFF3F414E)), textScaler: MediaQuery.textScalerOf(context)), "
        "textScaler: MediaQuery.textScalerOf(context))), fontSize: 16.0, "
        "fontWeight: FontWeight.w300, textAlign: TextAlign.left])"
    )
    fixed = sanitize_screen_emit_syntax(source)
    assert "copyWith(color: Color(0xFF3F414E), fontSize: 16.0" in fixed
    assert fixed.count("textScaler: MediaQuery.textScalerOf(context)") == 1
    assert "))), fontSize:" not in fixed
    assert "textAlign: TextAlign.left)" in fixed


def test_fallback_unparseable_screens_to_layout() -> None:
    path = "lib/features/sign_up/sign_up_screen.dart"
    planned = {
        path: "class SignUpScreen extends StatelessWidget { Widget build(c) => broken( ; }",
    }
    updated = fallback_unparseable_screens_to_layout(
        planned,
        (path,),
        package_name="demo_app",
    )
    assert "GeneratedScreenShell(child: const SignUpLayout())" in updated[path]
    assert "class GeneratedScreenShell extends StatelessWidget" in updated[path]
    assert "package:demo_app/generated/sign_up_layout.dart" in updated[path]


def test_fallback_imports_app_layout_when_prior_mentions_uri_without_import() -> None:
    """Oversized LLM screens can reference app_layout in body but not as import."""
    path = "lib/features/background/background_screen.dart"
    prior = (
        "// " + "x" * 8000
        + "package:demo_app/theme/app_layout.dart"
        + " AppBreakpoints.horizontalPadding(400)"
    )
    updated = fallback_unparseable_screens_to_layout(
        {path: prior},
        (path,),
        package_name="demo_app",
        responsive_enabled=True,
    )
    assert "import 'package:demo_app/theme/app_layout.dart';" in updated[path]
    assert "class GeneratedScreenShell extends StatelessWidget" in updated[path]
    assert "GeneratedScreenShell(child: const BackgroundLayout())" in updated[path]


def test_fallback_replaces_corrupt_generated_screen_shell() -> None:
    path = "lib/features/background/background_screen.dart"
    corrupt = (
        "/// Responsive shell injected by the generator for web/tablet max width.\n"
        "class GeneratedScreenShell extends StatelessWidget {\n"
        "  final Widget child;\n"
        ",,\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        "    return LayoutBuilder(;)\n"
        "  }\n"
        "}\n"
        "class BackgroundScreen extends StatelessWidget { broken( ; }"
    )
    updated = fallback_unparseable_screens_to_layout(
        {path: corrupt},
        (path,),
        package_name="demo_app",
    )
    assert ",," not in updated[path]
    assert "LayoutBuilder(;" not in updated[path]
    assert "return LayoutBuilder(" in updated[path]
    assert "GeneratedScreenShell(child: const BackgroundLayout())" in updated[path]


def test_repair_planned_format_parse_failures_inserts_missing_bracket() -> None:
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    path = "lib/features/sign_up/sign_up_screen.dart"
    planned = {
        path: "Widget build(BuildContext c) => Column(children: [Text('a'), Text('b'));"
    }
    errors = (
        "line 1, column 60 of /tmp/sign_up_screen.dart: Expected to find ']'.",
    )
    updated = repair_planned_format_parse_failures(
        planned,
        (path,),
        analyze_errors=errors,
    )
    assert validate_dart_delimiters(updated[path]) is None


def test_repair_planned_format_parse_failures_drops_garbage_line() -> None:
    path = "lib/features/sign_in/sign_in_screen.dart"
    garbage = "])))}}"
    lines = [
        "class X {",
        "  Widget build(BuildContext c) {",
        "    return Stack(",
        "      children: [",
        "        Text('a'),",
        garbage,
        "      ],",
        "    );",
        "  }",
        "}",
    ]
    planned = {path: "\n".join(lines)}
    errors = (
        "line 6, column 4 of /tmp/sign_in_screen.dart: Expected to find ';'.",
    )
    updated = repair_planned_format_parse_failures(
        planned,
        (path,),
        analyze_errors=errors,
    )
    assert "])))}}" not in updated[path]


def test_strip_orphan_semicolon_only_lines() -> None:
    source = "return Stack(\n  children: [\n    Text('a'),\n    ;\n  ],\n);"
    fixed = strip_orphan_semicolon_only_lines(source)
    assert is_orphan_semicolon_line(";")
    assert "\n    ;\n" not in fixed


def test_strip_duplicate_key_after_super() -> None:
    source = "const W({super.key, Key? key = null, required this.text});"
    fixed = strip_duplicate_key_after_super(source)
    assert "Key? key" not in fixed
    assert "super.key" in fixed


def test_strip_duplicate_key_trailing_before_close() -> None:
    source = (
        "const SocialButton({super.key, required this.text, "
        "required this.icon, Key? key});"
    )
    fixed = strip_duplicate_key_after_super(source)
    assert "Key? key" not in fixed


def test_fix_text_align_square_bracket_close() -> None:
    source = "Text('SIGN UP', textAlign: TextAlign.left],"
    fixed = fix_text_align_square_bracket_close(source)
    assert "textAlign: TextAlign.left)," in fixed
    assert "TextAlign.left]," not in fixed


def test_wrap_misplaced_text_style_params_on_text() -> None:
    source = """
    child: Text(
      'OR LOG IN WITH EMAIL',
      fontSize: 14.0,
      fontWeight: FontWeight.bold,
      letterSpacing: 0.7,
      fontFamilyFallback: ['Roboto'],
    ),
    """
    fixed = wrap_misplaced_text_style_params_on_text(source)
    assert "fontSize: 14.0" in fixed
    assert "style: TextStyle(" in fixed
    assert "Text(\n      'OR LOG IN WITH EMAIL',\n      fontSize:" not in fixed


def test_use_scale_down_for_design_canvas_fittedbox() -> None:
    source = """
    Center(
      child: FittedBox(
        fit: BoxFit.contain,
        child: SizedBox(width: 414, height: 896, child: Stack()),
      ),
    )
    """
    fixed = use_scale_down_for_design_canvas_fittedbox(source)
    assert "BoxFit.scaleDown" in fixed
    assert "BoxFit.contain" not in fixed


def test_fix_elevated_button_label_on_saturated_background() -> None:
    source = """
    ElevatedButton(
      style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF8E97FD)),
      child: Text('LOG IN', style: TextStyle(color: Color(0xFF000000), fontSize: 14.0)),
    )
    """
    fixed = fix_elevated_button_label_on_saturated_background(source)
    assert "Color(0xFFFFFFFF)" in fixed
    assert "Color(0xFF000000)" not in fixed


def test_wrap_misplaced_text_merges_into_existing_style() -> None:
    source = """
    Text(
      'ok',
      style: TextStyle(color: Color(0xFFA1A4B2)),
      fontSize: 14.0,
      fontWeight: FontWeight.w500,
    )
    """
    fixed = wrap_misplaced_text_style_params_on_text(source)
    assert "style: TextStyle(color: Color(0xFFA1A4B2), fontSize: 14.0" in fixed
    assert fixed.count("fontSize:") == 1


def test_wrap_misplaced_text_merges_font_weight_into_existing_style() -> None:
    source = """
    Text(
      'ok',
      style: TextStyle(fontSize: 12.0),
      fontWeight: FontWeight.bold,
    )
    """
    fixed = wrap_misplaced_text_style_params_on_text(source)
    assert "fontWeight: FontWeight.bold" in fixed
    assert fixed.count("fontSize:") == 1


def test_normalize_app_typography_style_references() -> None:
    source = """
    hintStyle: const AppTypography.emailAddress.copyWith(fontFamily: 'Helvetica Neue',
      'Arial', 'sans-serif'],
      color: Color(0xFFA1A4B2),
    ),
    """
    fixed = normalize_app_typography_style_references(source)
    assert "const AppTypography" not in fixed
    assert "'Arial', 'sans-serif']," not in fixed
    assert "AppTypography.emailAddress.copyWith" in fixed


def test_collapse_typography_strips_full_font_family_fallback() -> None:
    source = """
    style: TextStyle(
      fontSize: 16.0,
      fontWeight: FontWeight.w300,
      fontFamily: 'Helvetica Neue',
      fontFamilyFallback: ['Roboto', 'Arial', 'sans-serif'],
      color: Color(0xFFA1A4B2),
    ),
    """
    tokens = DesignTokens(
        typography={"emailAddress": TypographyStyle(font_size=16.0, font_weight="w300")},
    )
    collapsed = collapse_inline_text_styles_to_app_typography(source, tokens)
    assert "fontFamilyFallback" not in collapsed
    assert "'Arial', 'sans-serif']" not in collapsed
    assert "AppTypography.emailAddress" in collapsed


def test_collapse_preserves_theme_copywith_inside_text_rich() -> None:
    source = """
    Text.rich(
      TextSpan(
        children: [
          TextSpan(
            text: 'LOG IN',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Color(0xFF8E97FD),
              fontSize: 14.0,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
      textScaler: textScaler,
    )
    """
    tokens = DesignTokens(
        typography={"bodyLarge": TypographyStyle(font_size=14.0, font_weight="w700")},
    )
    collapsed = collapse_inline_text_styles_to_app_typography(source, tokens)
    assert "Theme.of(context).textTheme.bodyLarge?.copyWith" in collapsed
    assert collapsed.count("TextSpan(") >= 2


def test_collapse_skips_app_typography_definition_file() -> None:
    source = """
class AppTypography {
  static const TextStyle welcomeBack = TextStyle(fontSize: 28.0, fontWeight: FontWeight.w700);
}
"""
    tokens = DesignTokens(
        typography={"welcomeBack": TypographyStyle(font_size=28.0, font_weight="w700")},
    )
    collapsed = collapse_inline_text_styles_to_app_typography(source, tokens)
    assert "TextStyle(fontSize:" in collapsed
    assert "AppTypography.welcomeBack = AppTypography" not in collapsed
