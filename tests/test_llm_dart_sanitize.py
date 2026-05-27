"""Tests for LLM Dart sanitization."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.llm_dart import (
    _strip_class_definition,
    apply_clean_tree_text_to_screen,
    ensure_valid_llm_screen_code,
    ensure_valid_llm_widget_code,
    fix_invalid_positioned_constraints,
    normalize_llm_extracted_widget_code,
    normalize_llm_screen_class_name,
    prepare_llm_extracted_widgets,
    reconcile_extracted_widget_references,
    sanitize_figma_display_text,
    sanitize_llm_screen_code,
    sibling_widget_import_uris,
    validate_dart_delimiters,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
    TextSpanPart,
)


def test_strips_leading_imports_from_screen_code() -> None:
    source = """import 'package:flutter/material.dart';
import 'package:demo_app/theme/app_colors.dart';

class RemindersScreen extends StatelessWidget {
  const RemindersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}
"""
    sanitized = sanitize_llm_screen_code(source)
    assert "import " not in sanitized.split("class", 1)[0]
    assert "class RemindersScreen" in sanitized


def test_strips_duplicate_generated_screen_shell_class() -> None:
    source = """class GeneratedScreenShell extends StatelessWidget {
  const GeneratedScreenShell({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return child;
  }
}

class RemindersScreen extends StatelessWidget {
  const RemindersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return GeneratedScreenShell(child: const SizedBox());
  }
}
"""
    sanitized = sanitize_llm_screen_code(source, strip_generated_shell_class=True)
    assert "class GeneratedScreenShell" not in sanitized
    assert "GeneratedScreenShell(child:" in sanitized
    assert "class RemindersScreen" in sanitized


def test_validate_dart_delimiters_detects_unclosed_paren() -> None:
    source = """class Demo extends StatelessWidget {
  Widget build(BuildContext context) {
    return Column(
      children: [
        const SizedBox(),
      ),
    )
  }
}
"""
    error = validate_dart_delimiters(source)
    assert error is not None
    assert "Unclosed" in error or "Unexpected" in error


def test_ensure_valid_llm_screen_code_raises_on_invalid_delimiters() -> None:
    source = """class Demo extends StatelessWidget {
  Widget build(BuildContext context) {
    return Column(
  }
}
"""
    with pytest.raises(GenerationError, match="invalid Dart syntax"):
        ensure_valid_llm_screen_code(source)


def test_validate_dart_delimiters_ignores_braces_in_comments() -> None:
    source = """class Demo extends StatelessWidget {
  Widget build(BuildContext context) {
    // map entry: { hour: 1 }
    /* trailing brace } */
    return const SizedBox();
  }
}
"""
    assert validate_dart_delimiters(source) is None


def test_validate_dart_delimiters_ignores_braces_in_interpolation() -> None:
    source = """class Demo extends StatelessWidget {
  Widget build(BuildContext context) {
    final label = '${hour.toString().padLeft(2, '0')}';
    return Text(label);
  }
}
"""
    assert validate_dart_delimiters(source) is None


def test_validate_dart_delimiters_ignores_braces_in_triple_quoted_string() -> None:
    source = """class Demo extends StatelessWidget {
  Widget build(BuildContext context) {
    const payload = '''
    { "hour": 12 }
    ''';
    return const SizedBox();
  }
}
"""
    assert validate_dart_delimiters(source) is None


def test_ensure_valid_llm_widget_code_balances_missing_class_brace() -> None:
    source = """class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});
  @override
  Widget build(BuildContext context) {
    return SvgPicture.string(
      '<svg></svg>',
      width: 332.22,
      height: 242.69,
    );
  }
"""
    from figma_flutter_agent.generator.llm_dart import validate_dart_delimiters

    sanitized = ensure_valid_llm_widget_code(source, widget_name="GroupWidget")
    assert validate_dart_delimiters(sanitized) is None
    assert "class GroupWidget" in sanitized
    assert "SizedBox.shrink()" not in sanitized


def test_ensure_valid_llm_widget_code_uses_stub_when_unrepairable() -> None:
    source = """class BrokenWidget extends StatelessWidget {
  Widget build(BuildContext context) {
    return Column(
  }
"""
    sanitized = ensure_valid_llm_widget_code(source, widget_name="BrokenWidget")
    assert "SizedBox.shrink()" in sanitized


def test_normalize_llm_screen_class_name_renames_stateless_widget() -> None:
    source = """class MusicPlayerScreen extends StatelessWidget {
  const MusicPlayerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}
"""
    updated = normalize_llm_screen_class_name(source, "MusicV2Screen")
    assert "class MusicV2Screen extends StatelessWidget" in updated
    assert "const MusicV2Screen(" in updated
    assert "MusicPlayerScreen" not in updated


def test_normalize_llm_screen_class_name_renames_stateful_widget_and_state() -> None:
    source = """class MusicPlayerScreen extends StatefulWidget {
  const MusicPlayerScreen({super.key});

  @override
  State<MusicPlayerScreen> createState() => _MusicPlayerScreenState();
}

class _MusicPlayerScreenState extends State<MusicPlayerScreen> {
  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}
"""
    updated = normalize_llm_screen_class_name(source, "MusicV2Screen")
    assert "class MusicV2Screen extends StatefulWidget" in updated
    assert "State<MusicV2Screen>" in updated
    assert "_MusicV2ScreenState" in updated
    assert "MusicPlayerScreen" not in updated


def test_dedupe_primary_widget_class_keeps_first_screen() -> None:
    from figma_flutter_agent.generator.llm_dart import dedupe_primary_widget_class

    source = """
class SignUpAndSignInScreen extends StatelessWidget {
  const SignUpAndSignInScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}

class SignUpAndSignInScreen extends StatefulWidget {
  const SignUpAndSignInScreen({super.key});

  @override
  State<SignUpAndSignInScreen> createState() => _SignUpAndSignInScreenState();
}

class _SignUpAndSignInScreenState extends State<SignUpAndSignInScreen> {
  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}
"""
    updated = dedupe_primary_widget_class(source, "SignUpAndSignInScreen")
    assert updated.count("class SignUpAndSignInScreen") == 1
    assert "extends StatelessWidget" in updated
    assert "extends StatefulWidget" not in updated
    assert "_SignUpAndSignInScreenState" not in updated


def test_ensure_valid_llm_screen_code_renames_to_expected_class() -> None:
    source = """class MusicPlayerScreen extends StatelessWidget {
  const MusicPlayerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}
"""
    updated = ensure_valid_llm_screen_code(
        source,
        expected_screen_class="MusicV2Screen",
    )
    assert "class MusicV2Screen" in updated


def test_normalize_llm_extracted_widget_code_renames_private_class() -> None:
    source = """class _CircleAction extends StatelessWidget {
  const _CircleAction({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Icon(icon);
  }
}
"""
    updated, actual, canonical = normalize_llm_extracted_widget_code(
        source,
        widget_name="CircleAction",
    )
    assert actual == "_CircleAction"
    assert canonical == "CircleAction"
    assert "class CircleAction extends StatelessWidget" in updated
    assert "const CircleAction(" in updated


def test_reconcile_extracted_widget_references_rewrites_screen_usages() -> None:
    widget_code = """class _CircleAction extends StatelessWidget {
  const _CircleAction({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Icon(icon);
  }
}
"""
    screen_code = """class MusicV2Screen extends StatelessWidget {
  const MusicV2Screen({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      _CircleAction(icon: Icons.share),
      _CircleAction(icon: Icons.download),
    ]);
  }
}
"""
    updated = reconcile_extracted_widget_references(
        screen_code,
        [("CircleAction", widget_code)],
    )
    assert "_CircleAction(" not in updated
    assert "CircleAction(icon: Icons.share)" in updated


def test_prepare_llm_extracted_widgets_assigns_unique_class_names() -> None:
    first = """class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    second = """class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox(width: 2);
}
"""
    prepared, class_to_file = prepare_llm_extracted_widgets(
        [
            ("GroupWidget", first),
            ("GroupWidget", second),
        ]
    )
    codes = [code for _, code in prepared]
    assert any("class GroupWidget extends StatelessWidget" in code for code in codes)
    assert any("class GroupWidget2 extends StatelessWidget" in code for code in codes)
    assert class_to_file["GroupWidget"] == "group_widget"
    assert class_to_file["GroupWidget2"] == "group_widget"


def test_prepare_llm_extracted_widgets_reconciles_nested_sibling_references() -> None:
    control_code = """class _ControlCircleIcon extends StatelessWidget {
  const _ControlCircleIcon({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Icon(icon);
  }
}
"""
    player_code = """class PlayerControls extends StatelessWidget {
  const PlayerControls({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      ControlCircleIcon(icon: Icons.share),
      ControlCircleIcon(icon: Icons.download),
    ]);
  }
}
"""
    prepared, class_to_file = prepare_llm_extracted_widgets(
        [
            ("ControlCircleIcon", control_code),
            ("PlayerControls", player_code),
        ]
    )
    prepared_by_name = dict(prepared)
    assert (
        "class ControlCircleIcon extends StatelessWidget" in prepared_by_name["ControlCircleIcon"]
    )
    assert "ControlCircleIcon(icon: Icons.share)" in prepared_by_name["PlayerControls"]
    assert class_to_file["ControlCircleIcon"] == "control_circle_icon"

    imports = sibling_widget_import_uris(
        prepared_by_name["PlayerControls"],
        own_class="PlayerControls",
        class_to_file=class_to_file,
        uri_for_path=lambda path: f"package:demo_app/{path}",
    )
    assert imports == ["package:demo_app/widgets/control_circle_icon.dart"]


def test_reconcile_extracted_widget_references_strips_duplicate_without_breaking_screen_state() -> (
    None
):
    control_code = """class _ControlCircleIcon extends StatelessWidget {
  const _ControlCircleIcon({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Icon(icon);
  }
}
"""
    screen_code = """class MusicV2Screen extends StatefulWidget {
  const MusicV2Screen({super.key});

  @override
  State<MusicV2Screen> createState() => _MusicV2ScreenState();
}

class _MusicV2ScreenState extends State<MusicV2Screen> {
  @override
  Widget build(BuildContext context) {
    return const PlayerControls();
  }
}

class ControlCircleIcon extends StatelessWidget {
  const ControlCircleIcon({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Icon(icon);
  }
}
"""
    updated = reconcile_extracted_widget_references(
        screen_code,
        [
            ("ControlCircleIcon", control_code),
            (
                "PlayerControls",
                "class PlayerControls extends StatelessWidget { const PlayerControls({super.key}); @override Widget build(BuildContext c) => SizedBox(); }",
            ),
        ],
    )
    assert "class ControlCircleIcon extends StatelessWidget" not in updated
    assert "class _MusicV2ScreenState extends State<MusicV2Screen>" in updated
    assert validate_dart_delimiters(updated) is None


def test_normalize_text_for_match_decodes_dart_newline_escapes() -> None:
    from figma_flutter_agent.generator.llm_dart import _normalize_text_for_match

    figma_norm = _normalize_text_for_match("line one\nline two")
    dart_norm = _normalize_text_for_match(r"line one\nline two", from_dart_literal=True)
    assert figma_norm == dart_norm == "line one line two"


def test_sanitize_figma_display_text_strips_trailing_newline_and_spaces() -> None:
    assert sanitize_figma_display_text("We are what we do\n") == "We are what we do"
    assert (
        sanitize_figma_display_text("Thousand of people are usign silent moon  \nfor smalls meditation ")
        == "Thousand of people are usign silent moon\nfor smalls meditation"
    )


def test_apply_clean_tree_text_fixes_duplicate_login_and_three_line_copy() -> None:
    login = CleanDesignTreeNode(
        id="1:3973",
        name="login",
        type=NodeType.TEXT,
        text="ALREADY HAVE AN ACCOUNT? LOG IN",
        style=NodeStyle(font_size=14.0, text_color="0xFFA1A4B2"),
        text_spans=[
            TextSpanPart(text="ALREADY HAVE AN ACCOUNT?", text_color="0xFFA1A4B2"),
            TextSpanPart(text=" "),
            TextSpanPart(text="LOG IN", text_color="0xFF8E97FD", is_link=True),
        ],
    )
    subtitle = CleanDesignTreeNode(
        id="1:3976",
        name="subtitle",
        type=NodeType.TEXT,
        text="Thousand of people are usign silent moon  \nfor smalls meditation ",
        style=NodeStyle(font_size=16.0, text_color="0xFFA1A4B2"),
        sizing=Sizing(width=298.0),
    )
    tree = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.COLUMN,
        children=[login, subtitle],
    )
    screen = """
    RichText(
      textAlign: TextAlign.center,
      text: TextSpan(
        children: [
          TextSpan(
            text: 'ALREADY HAVE AN ACCOUNT? LOG IN',
            style: TextStyle(color: theme.colorScheme.secondary),
          ),
          TextSpan(
            text: 'LOG IN',
            style: TextStyle(color: theme.colorScheme.primary),
          ),
        ],
      ),
    ),
    Text(
      'Thousand of people are usign silent moon \nfor smalls meditation',
      style: theme.textTheme.bodyMedium,
      textScaler: MediaQuery.textScalerOf(context),
    ),
    """
    updated = apply_clean_tree_text_to_screen(screen, tree)
    assert "'ALREADY HAVE AN ACCOUNT? LOG IN'" not in updated
    assert "TextSpan(text: 'ALREADY HAVE AN ACCOUNT?'," in updated
    assert "TextSpan(text: 'LOG IN'," in updated
    assert "Column(" in updated
    assert "softWrap: false" in updated
    assert "Thousand of people are usign silent moon" in updated
    assert "for smalls meditation" in updated
    assert "maxLines: 1" not in updated
    assert "maxLines: 2" not in updated


def test_split_two_line_skips_already_split_first_line() -> None:
    from figma_flutter_agent.generator.llm_dart import (
        _split_two_line_text_widget,
        sanitize_figma_display_text,
    )

    sanitized = sanitize_figma_display_text(
        "Thousand of people are usign silent moon  \nfor smalls meditation "
    )
    screen = """
    Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('Thousand of people are usign silent moon', softWrap: false, style: TextStyle()),
        Text('for smalls meditation', softWrap: false, style: TextStyle()),
      ],
    )
    """
    assert _split_two_line_text_widget(screen, sanitized) == screen


def test_split_two_line_avoids_soft_wrap_reflow() -> None:
    from figma_flutter_agent.generator.llm_dart import (
        _split_two_line_text_widget,
        sanitize_figma_display_text,
    )

    sanitized = sanitize_figma_display_text(
        "Thousand of people are usign silent moon  \nfor smalls meditation "
    )
    screen = """
    Text(
      'Thousand of people are usign silent moon\\nfor smalls meditation',
      textAlign: TextAlign.center,
      maxLines: 2,
      softWrap: true,
      style: TextStyle(fontSize: 16.0, height: 1.65),
    )
    """
    patched = _split_two_line_text_widget(screen, sanitized)
    assert "maxLines: 2" not in patched
    assert "softWrap: true" not in patched
    assert "Text('Thousand of people are usign silent moon'" in patched
    assert "Text('for smalls meditation'" in patched


def test_collapse_rigid_two_line_copy_column() -> None:
    from figma_flutter_agent.generator.llm_dart import (
        _collapse_rigid_two_line_copy_column,
        sanitize_figma_display_text,
    )

    sanitized = sanitize_figma_display_text(
        "Thousand of people are usign silent moon  \nfor smalls meditation "
    )
    screen = """
    Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'Thousand of people are usign silent moon',
          textAlign: TextAlign.center,
          maxLines: 1,
          softWrap: false,
          style: TextStyle(fontSize: 16.0, height: 1.65),
        ),
        Text(
          'for smalls meditation',
          textAlign: TextAlign.center,
          maxLines: 1,
          softWrap: false,
          style: TextStyle(fontSize: 16.0, height: 1.65),
        ),
      ],
    )
    """
    patched = _collapse_rigid_two_line_copy_column(screen, sanitized)
    assert "softWrap: false" in patched
    assert "for smalls meditation" in patched
    assert "maxLines: 1" not in patched
    assert "maxLines: 2" not in patched
    assert "height: 1.65" in patched


def test_patch_multiline_copy_column_width_drops_positioned_height() -> None:
    from figma_flutter_agent.generator.llm_dart import _patch_multiline_copy_column_width

    screen = """
    Positioned(
      left: 58.0,
      top: 534.0,
      width: 274.0,
      height: 109.0,
      child: Column(
        children: [
          Text('line one\\nline two', maxLines: 2),
        ],
      ),
    ),
    """
    patched = _patch_multiline_copy_column_width(screen, 298.0)
    assert "width: 315.9" in patched
    assert "height: 109" not in patched


def test_patch_multiline_copy_column_width_when_width_before_top() -> None:
    from figma_flutter_agent.generator.llm_dart import _patch_multiline_copy_column_width

    screen = """
    Positioned(
      left: 58.0,
      width: 274.0,
      top: 120.0,
      child: Column(
        children: [
          Text('line one\\nline two'),
        ],
      ),
    ),
    """
    patched = _patch_multiline_copy_column_width(screen, 298.0)
    assert "width: 315.9" in patched
    assert "width: 274" not in patched


def test_patch_multiline_copy_strips_height_for_split_subtitle_lines() -> None:
    from figma_flutter_agent.generator.llm_dart import _strip_multiline_copy_positioned_heights

    screen = """
    Positioned(
      left: 58.0,
      top: 534.0,
      width: 298.0,
      height: 120.0,
      child: Column(
        children: [
          Text('title', style: TextStyle(fontSize: 30.0)),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('line one', softWrap: false, style: TextStyle(fontSize: 16.0)),
              Text('line two', softWrap: false, style: TextStyle(fontSize: 16.0)),
            ],
          ),
        ],
      ),
    ),
    """
    patched = _strip_multiline_copy_positioned_heights(screen)
    assert "height: 120" not in patched


def test_apply_fitted_box_to_multiline_copy_lines() -> None:
    from figma_flutter_agent.generator.llm_dart import _apply_fitted_box_to_multiline_copy_lines

    screen = """
    Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('line one', softWrap: false, style: TextStyle()),
        Text('line two', softWrap: false, style: TextStyle()),
      ],
    )
    """
    patched = _apply_fitted_box_to_multiline_copy_lines(screen)
    assert patched.count("FittedBox(") == 2
    assert patched.count("BoxFit.scaleDown") == 2


def test_multiline_copy_text_widget_uses_fitted_box() -> None:
    from figma_flutter_agent.generator.llm_dart import (
        _multiline_copy_text_widget,
        sanitize_figma_display_text,
    )

    sanitized = sanitize_figma_display_text("line one\nline two")
    widget = _multiline_copy_text_widget(
        sanitized_text=sanitized,
        style_expr="TextStyle(fontSize: 16.0)",
        align_prefix="textAlign: TextAlign.center, ",
    )
    assert widget.count("FittedBox(") == 2


def test_patch_material_button_matches_any_figma_label() -> None:
    from figma_flutter_agent.generator.llm_dart import _patch_material_buttons_from_tree

    tree = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="1",
                name="actions",
                type=NodeType.STACK,
                children=[
                    CleanDesignTreeNode(
                        id="2",
                        name="pill",
                        type=NodeType.CONTAINER,
                        style=NodeStyle(
                            background_color="0xFF112233",
                            border_radius=24.0,
                        ),
                    ),
                    CleanDesignTreeNode(
                        id="3",
                        name="label",
                        type=NodeType.TEXT,
                        text="Continue",
                        style=NodeStyle(
                            text_color="0xFF000000",
                            css_properties={"color": "rgba(255, 255, 255, 1.000)"},
                        ),
                    ),
                ],
            ),
        ],
    )
    screen = """
    FilledButton(
      style: FilledButton.styleFrom(
        backgroundColor: Theme.of(context).colorScheme.primary,
      ),
      child: Text(
        'Continue',
        style: TextStyle(color: Theme.of(context).colorScheme.onPrimary),
      ),
    )
    """
    patched = _patch_material_buttons_from_tree(screen, tree)
    assert "Color(0xFF112233)" in patched
    assert "Color(0xFFFFFFFF)" in patched


def test_patch_sign_up_button_uses_figma_purple_not_theme_primary() -> None:
    from figma_flutter_agent.generator.llm_dart import apply_clean_tree_text_to_screen

    button_container = CleanDesignTreeNode(
        id="1:3971",
        name="Rectangle",
        type=NodeType.CONTAINER,
        style=NodeStyle(background_color="0xFF8E97FD"),
    )
    label = CleanDesignTreeNode(
        id="1:3972",
        name="SIGN UP",
        type=NodeType.TEXT,
        text="SIGN UP",
        style=NodeStyle(
            text_color="0xFF000000",
            css_properties={"color": "rgba(246, 241, 251, 1.000)"},
        ),
    )
    tree = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.COLUMN,
        children=[button_container, label],
    )
    screen = """
    final ThemeData theme = Theme.of(context).copyWith();
    return Theme(
      data: theme,
      child: FilledButton(
        style: FilledButton.styleFrom(
          backgroundColor: Theme.of(context).colorScheme.primary,
        ),
        child: Text(
          'SIGN UP',
          style: TextStyle(color: Theme.of(context).colorScheme.onPrimary),
        ),
      ),
    );
    """
    patched = apply_clean_tree_text_to_screen(screen, tree)
    assert "Color(0xFF8E97FD)" in patched
    assert "Color(0xFFF6F1FB)" in patched
    assert "Color(0xFF000000)" not in patched
    assert "Theme.of(context).colorScheme.primary" not in patched


def test_apply_clean_tree_text_splits_double_quoted_subtitle() -> None:
    subtitle = CleanDesignTreeNode(
        id="1:3976",
        name="subtitle",
        type=NodeType.TEXT,
        text="Thousand of people are usign silent moon  \nfor smalls meditation ",
        style=NodeStyle(font_size=16.0, text_color="0xFFA1A4B2"),
    )
    tree = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.COLUMN,
        children=[subtitle],
    )
    screen = """
    Text(
      "Thousand of people are usign silent moon \\nfor smalls meditation",
      style: theme.textTheme.bodyMedium,
      textScaler: MediaQuery.textScalerOf(context),
    ),
    """
    updated = apply_clean_tree_text_to_screen(screen, tree)
    assert "softWrap: false" in updated
    assert "for smalls meditation" in updated
    assert '"Thousand of people are usign silent moon \\nfor smalls meditation"' not in updated


def test_relax_tight_text_positioned_heights_expands_divider_label() -> None:
    divider = CleanDesignTreeNode(
        id="1:3599",
        name="OR LOG IN WITH EMAIL",
        type=NodeType.TEXT,
        text="OR LOG IN WITH EMAIL",
        style=NodeStyle(
            font_size=14.0,
            font_weight="w700",
            line_height=1.08,
            letter_spacing=0.7,
        ),
        stack_placement=StackPlacement(left=112.0, top=390.0, width=188.0, height=14.0),
    )
    tree = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.STACK,
        children=[divider],
    )
    screen = """
    Positioned(
      left: 112.0,
      top: 390.0,
      width: 188.0,
      height: 14.0,
      child: Center(
        child: Text('OR LOG IN WITH EMAIL'),
      ),
    ),
    """
    updated = apply_clean_tree_text_to_screen(screen, tree)
    assert "height: 14.0" not in updated
    assert "height: 17.1" in updated or "height: 17," in updated


def test_fix_invalid_positioned_constraints_drops_width_with_left_and_right() -> None:
    screen = """
    Positioned(
      left: 40.0,
      width: 315.9,
      right: 40.0,
      top: 430.0,
      child: Column(children: []),
    ),
    """
    fixed = fix_invalid_positioned_constraints(screen)
    assert "width: 315.9" not in fixed
    assert "left: 40.0" in fixed
    assert "right: 40.0" in fixed


def test_ensure_valid_llm_screen_code_strips_conflicting_positioned_width() -> None:
    source = """
class DemoScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      Positioned(left: 1.0, width: 10.0, right: 2.0, top: 3.0, child: SizedBox()),
    ]);
  }
}
"""
    sanitized = ensure_valid_llm_screen_code(source)
    assert "width: 10.0" not in sanitized


def test_strip_class_definition_does_not_use_constructor_parameter_brace() -> None:
    source = """class DuplicateWidget extends StatelessWidget
  const DuplicateWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox();
  }
}
"""
    stripped = _strip_class_definition(source, "DuplicateWidget", ("StatelessWidget",))
    assert stripped == source
