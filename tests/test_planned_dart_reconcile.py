import re

from figma_flutter_agent.generator.dart_postprocess import (
    fix_llm_dart_api_mistakes,
    fix_malformed_closure_syntax,
    postprocess_generated_dart,
)
from figma_flutter_agent.generator.planned_dart import (
    _sanitize_screen_dart_syntax,
    _scoped_ast_reconcile_paths,
    align_widget_class_with_file_stem,
    ensure_referenced_widget_imports,
    ensure_widget_sibling_imports,
    prune_duplicate_widget_classes,
    prune_disk_widget_stem_aliases,
    reconcile_cluster_variant_args,
    reconcile_planned_dart_files,
    redirect_widget_imports_to_canonical,
    strip_ambiguous_widget_imports,
    strip_inline_widget_duplicates_from_screens,
    strip_llm_relative_widget_imports,
    sync_widget_class_constructors,
)
from figma_flutter_agent.generator.validation import (
    collect_analyze_error_lines,
    normalize_analyzer_errors_for_fingerprint,
    parse_format_errors,
)


def test_fix_malformed_closure_syntax_rewrites_empty_closure_comma() -> None:
    source = "GestureDetector(onTap: () {, child: SizedBox())"
    updated = fix_malformed_closure_syntax(source)
    assert updated == "GestureDetector(onTap: () {}, child: SizedBox())"


def test_fix_llm_dart_api_mistakes_wraps_material_on_pressed_with_block_body() -> None:
    source = """
return Material(
  color: Colors.transparent,
  onPressed: () {
    onSignUp();
  },
  child: SizedBox(),
);
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "GestureDetector(onTap: () {" in updated
    assert "onSignUp();" in updated
    assert "child: Material(" in updated
    assert "onPressed:" not in updated


def test_fix_llm_dart_api_mistakes_adds_gestures_import_for_tap_recognizer() -> None:
    source = """
import 'package:flutter/material.dart';

class Demo extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Text.rich(
      TextSpan(
        recognizer: TapGestureRecognizer()..onTap = () {},
      ),
    );
  }
}
"""
    updated = postprocess_generated_dart(source)
    assert "import 'package:flutter/gestures.dart';" in updated


def test_fix_llm_dart_api_mistakes_adds_missing_button_on_pressed() -> None:
    source = """
return ElevatedButton(
  child: Text('SIGN UP'),
);
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "onPressed: () {}" in updated


def test_strip_llm_relative_widget_imports_removes_bare_widget_paths() -> None:
    source = """
// Import prebuilt dependencies as mandated by structural invariants
import 'group6795_widget.dart';

class SignInScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    stripped = strip_llm_relative_widget_imports(source)
    assert "group6795_widget.dart" not in stripped
    assert "Import prebuilt dependencies" not in stripped
    assert "class SignInScreen" in stripped


def test_ensure_referenced_widget_imports_adds_missing_screen_import() -> None:
    planned = {
        "lib/widgets/group_widget.dart": """
class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
        "lib/features/demo/demo_screen.dart": """
import 'package:flutter/material.dart';
import 'package:demo_app/theme/app_layout.dart';

class DemoScreen extends StatelessWidget {
  const DemoScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return const GroupWidget();
  }
}
""",
    }
    updated = ensure_referenced_widget_imports(planned)
    screen = updated["lib/features/demo/demo_screen.dart"]
    assert "import 'package:demo_app/widgets/group_widget.dart';" in screen


def test_ensure_referenced_widget_imports_adds_missing_layout_import() -> None:
    planned = {
        "lib/widgets/group17_widget.dart": """
class Group17Widget extends StatelessWidget {
  const Group17Widget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
        "lib/generated/sign_up_and_sign_in_layout.dart": """
import 'package:flutter/material.dart';

class SignUpAndSignInLayout extends StatelessWidget {
  const SignUpAndSignInLayout({super.key});
  @override
  Widget build(BuildContext context) => const Group17Widget();
}
""",
    }
    updated = ensure_referenced_widget_imports(planned)
    layout = updated["lib/generated/sign_up_and_sign_in_layout.dart"]
    assert "import 'package:demo_app/widgets/group17_widget.dart';" in layout


def test_widget_import_stems_for_screen_prefers_largest_widget_file() -> None:
    from figma_flutter_agent.generator.planned_dart import widget_import_stems_for_screen

    planned = {
        "lib/widgets/group_widget.dart": "class GroupWidget extends StatelessWidget { " + ("x" * 200) + " }",
        "lib/widgets/group_widget_2.dart": "class GroupWidget extends StatelessWidget {}",
    }
    stems = widget_import_stems_for_screen(
        "return const GroupWidget();",
        planned,
    )
    assert stems == ["group_widget"]


def test_prune_duplicate_widget_classes_keeps_canonical_file() -> None:
    planned = {
        "lib/widgets/group_widget.dart": "class GroupWidget extends StatelessWidget { " + ("x" * 200) + " }",
        "lib/widgets/group_widget_2.dart": "class GroupWidget extends StatelessWidget {}",
    }
    updated = prune_duplicate_widget_classes(planned)
    assert "lib/widgets/group_widget.dart" in updated
    assert "lib/widgets/group_widget_2.dart" not in updated


def test_strip_ambiguous_widget_imports_removes_duplicate_class_import() -> None:
    planned = {
        "lib/widgets/group_widget.dart": "class GroupWidget extends StatelessWidget {}",
        "lib/widgets/group_widget_2.dart": "class GroupWidget extends StatelessWidget {}",
    }
    screen = """
import 'package:flutter/material.dart';
import 'package:demo_app/widgets/group_widget.dart';
import 'package:demo_app/widgets/group_widget_2.dart';

class DemoScreen extends StatelessWidget {
  const DemoScreen({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget();
}
"""
    updated = strip_ambiguous_widget_imports(
        screen,
        planned,
        source_file="lib/features/demo/demo_screen.dart",
    )
    assert "group_widget.dart" in updated
    assert "group_widget_2.dart" not in updated


def test_scoped_ast_reconcile_paths_feature_screens_only() -> None:
    planned = {
        "lib/features/sign_in/sign_in_screen.dart": "class A {}",
        "lib/generated/sign_in_layout.dart": "class L {}",
        "lib/widgets/foo.dart": "class W {}",
        "lib/theme/app_colors.dart": "class C {}",
        "lib/main.dart": "void main() {}",
        "test/golden/sign_in_screen_test.dart": "void main() {}",
    }
    scoped = _scoped_ast_reconcile_paths(planned)
    assert scoped == frozenset({"lib/features/sign_in/sign_in_screen.dart"})


def test_reconcile_planned_dart_files_prunes_duplicate_group_widgets() -> None:
    planned = {
        "lib/widgets/group_widget.dart": "class GroupWidget extends StatelessWidget { " + ("x" * 200) + " }",
        "lib/widgets/group_widget_2.dart": "class GroupWidget extends StatelessWidget {}",
        "lib/features/demo/demo_screen.dart": """
import 'package:flutter/material.dart';
import 'package:demo_app/widgets/group_widget.dart';
import 'package:demo_app/widgets/group_widget_2.dart';

class DemoScreen extends StatelessWidget {
  const DemoScreen({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget();
}
""",
    }
    updated = reconcile_planned_dart_files(planned)
    assert "lib/widgets/group_widget_2.dart" not in updated
    screen = updated["lib/features/demo/demo_screen.dart"]
    assert "group_widget_2.dart" not in screen


def test_reconcile_planned_dart_files_dedupes_duplicate_screen_class() -> None:
    planned = {
        "lib/features/sign_up_and_sign_in/sign_up_and_sign_in_screen.dart": """
import 'package:flutter/material.dart';

class SignUpAndSignInScreen extends StatelessWidget {
  const SignUpAndSignInScreen({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}

class SignUpAndSignInScreen extends StatefulWidget {
  const SignUpAndSignInScreen({super.key});
  @override
  State<SignUpAndSignInScreen> createState() => _SignUpAndSignInScreenState();
}

class _SignUpAndSignInScreenState extends State<SignUpAndSignInScreen> {
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
    }
    updated = reconcile_planned_dart_files(planned)
    screen = updated["lib/features/sign_up_and_sign_in/sign_up_and_sign_in_screen.dart"]
    assert screen.count("class SignUpAndSignInScreen") == 1
    assert "extends StatefulWidget" not in screen


def test_reconcile_cluster_variant_args_strips_is_forward_from_layout() -> None:
    planned = {
        "lib/widgets/group_widget.dart": """
class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
        "lib/generated/sign_up_layout.dart": """
class SignUpLayout extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      const GroupWidget(isForward: false),
      const GroupWidget(),
    ]);
  }
}
""",
    }
    updated = reconcile_cluster_variant_args(planned)
    layout = updated["lib/generated/sign_up_layout.dart"]
    assert "isForward" not in layout
    assert "const GroupWidget()" in layout


def test_sync_widget_class_constructors_fixes_mismatched_const_name() -> None:
    source = """
class GroupWidget extends StatelessWidget {
  const GroupWidget2({super.key});

  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    updated = sync_widget_class_constructors(source)
    assert "const GroupWidget({" in updated
    assert "GroupWidget2" not in updated


def test_sync_widget_build_class_references_fixes_numbered_alias_in_build() -> None:
    source = """
class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return const GroupWidget2();
  }
}
"""
    updated = sync_widget_class_constructors(source)
    assert "const GroupWidget()" in updated
    assert "GroupWidget2" not in updated


def test_sync_widget_class_constructors_leaves_valid_constructor_alone() -> None:
    source = """
class CustomInputField extends StatelessWidget {
  const CustomInputField({
    super.key,
    required this.controller,
    required this.hintText,
  });

  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    assert sync_widget_class_constructors(source) == source


def test_sanitize_screen_dart_syntax_drops_orphan_commas() -> None:
    source = """
return Stack(children: [
  const Text('Hi'),
      ,
    ,
  ]);
"""
    fixed = _sanitize_screen_dart_syntax(source)
    assert re.search(r"^\s*,\s*$", fixed, flags=re.MULTILINE) is None


def test_ensure_widget_sibling_imports_adds_cross_widget_import() -> None:
    planned = {
        "lib/widgets/group_widget.dart": """
import 'package:flutter/material.dart';

class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
        "lib/widgets/group_widget_2.dart": """
import 'package:flutter/material.dart';

class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget();
}
""",
    }
    updated = ensure_widget_sibling_imports(planned)
    widget2 = updated["lib/widgets/group_widget_2.dart"]
    assert "import 'package:demo_app/widgets/group_widget.dart';" in widget2


def test_align_widget_class_with_file_stem() -> None:
    from figma_flutter_agent.generator.planned_dart import align_widget_class_with_file_stem

    planned = {
        "lib/widgets/group_widget_2.dart": """
import 'package:flutter/material.dart';

class GroupWidget extends StatelessWidget {
  const GroupWidget({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
    }
    updated = align_widget_class_with_file_stem(planned)
    assert "class GroupWidget2 extends" in updated["lib/widgets/group_widget_2.dart"]
    assert "const GroupWidget2(" in updated["lib/widgets/group_widget_2.dart"]


def test_prepare_files_for_write_commit_includes_layout_and_widget() -> None:
    from figma_flutter_agent.generator.planned_dart import prepare_files_for_write_commit

    planned = {
        "lib/widgets/group_widget2.dart": """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
        "lib/generated/sign_up_layout.dart": """
import 'package:flutter/material.dart';
import 'package:demo_app/widgets/group_widget_2.dart';

class SignUpLayout extends StatelessWidget {
  const SignUpLayout({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget2();
}
""",
    }
    prepared = prepare_files_for_write_commit(
        {"lib/widgets/group_widget2.dart": planned["lib/widgets/group_widget2.dart"]},
        planned,
    )
    layout = prepared["lib/generated/sign_up_layout.dart"]
    assert "widgets/group_widget2.dart" in layout
    assert "widgets/group_widget_2.dart" not in layout


def test_consolidate_planned_widget_paths_merges_alias_file() -> None:
    from figma_flutter_agent.generator.planned_dart import consolidate_planned_widget_paths

    planned = {
        "lib/widgets/group_widget_2.dart": """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox(width: 1);
}
""",
        "lib/widgets/group_widget2.dart": """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget2();
}
""",
    }
    updated = consolidate_planned_widget_paths(planned)
    assert "lib/widgets/group_widget_2.dart" not in updated
    assert "SizedBox(width: 1)" in updated["lib/widgets/group_widget2.dart"]


def test_redirect_widget_imports_to_canonical_fixes_stale_uri(tmp_path) -> None:
    from figma_flutter_agent.generator.planned_dart import consolidate_planned_widget_paths

    planned = {
        "lib/widgets/group_widget2.dart": """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
        "lib/generated/sign_up_layout.dart": """
import 'package:flutter/material.dart';
import 'package:demo_app/widgets/group_widget_2.dart';

class SignUpLayout extends StatelessWidget {
  const SignUpLayout({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget2();
}
""",
    }
    planned = consolidate_planned_widget_paths(planned)
    updated = redirect_widget_imports_to_canonical(planned)
    layout = updated["lib/generated/sign_up_layout.dart"]
    assert "widgets/group_widget2.dart" in layout
    assert "widgets/group_widget_2.dart" not in layout


def test_prune_disk_widget_stem_aliases_removes_duplicate_file(tmp_path) -> None:
    widgets = tmp_path / "lib" / "widgets"
    widgets.mkdir(parents=True)
    good = """
import 'package:flutter/material.dart';

class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox(width: 10);
}
"""
    (widgets / "group_widget_2.dart").write_text(good, encoding="utf-8")
    (widgets / "group_widget2.dart").write_text(
        """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget2();
}
""",
        encoding="utf-8",
    )
    planned = {"lib/widgets/group_widget2.dart": good}
    removed = prune_disk_widget_stem_aliases(tmp_path, planned)
    assert "lib/widgets/group_widget_2.dart" in removed
    assert not (widgets / "group_widget_2.dart").exists()
    assert (widgets / "group_widget2.dart").exists()


def test_absorb_disk_widget_alias_bodies_replaces_stub(tmp_path) -> None:
    from figma_flutter_agent.generator.planned_dart import absorb_disk_widget_alias_bodies

    widgets = tmp_path / "lib" / "widgets"
    widgets.mkdir(parents=True)
    good = """
import 'package:flutter/material.dart';
import 'package:demo_app/widgets/group_widget.dart';

class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget();
}
"""
    (widgets / "group_widget_2.dart").write_text(good, encoding="utf-8")
    planned = {
        "lib/widgets/group_widget2.dart": """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const GroupWidget2();
}
""",
    }
    updated = absorb_disk_widget_alias_bodies(planned, tmp_path)
    assert "const GroupWidget()" in updated["lib/widgets/group_widget2.dart"]
    assert "const GroupWidget2()" not in updated["lib/widgets/group_widget2.dart"]


def test_repair_self_referential_replaces_context_widget_return() -> None:
    from figma_flutter_agent.generator.planned_dart import repair_self_referential_widget_builds

    planned = {
        "lib/widgets/group_widget2.dart": """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) {
    return context.widget;
  }
}
""",
    }
    updated = repair_self_referential_widget_builds(planned)
    assert "lib/widgets/group_widget2.dart" not in updated


def test_prune_duplicate_widget_drops_self_referential_stub() -> None:
    planned = {
        "lib/widgets/group_widget2.dart": """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) {
    return const GroupWidget2();
  }
}
""",
        "lib/widgets/group_widget_2.dart": """
class GroupWidget2 extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) {
    return Stack(children: [SvgPicture.asset('assets/icons/a.svg')]);
  }
}
""",
    }
    updated = reconcile_planned_dart_files(planned)
    assert "lib/widgets/group_widget_2.dart" not in updated
    assert "SvgPicture.asset" in updated["lib/widgets/group_widget2.dart"]
    assert "const GroupWidget2()" not in updated["lib/widgets/group_widget2.dart"]


def test_reconcile_fixes_widget_constructor_mismatch() -> None:
    planned = {
        "lib/widgets/group_widget.dart": """
class GroupWidget extends StatelessWidget {
  const GroupWidget2({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
""",
    }
    updated = reconcile_planned_dart_files(planned)
    assert "const GroupWidget({" in updated["lib/widgets/group_widget.dart"]


def test_parse_format_errors_extracts_parser_diagnostics() -> None:
    details = """
Formatted 3 files (3 changed) in 0.1 seconds.
Could not format because the source could not be parsed:

line 30, column 36 of lib/widgets/action_section.dart: Expected an identifier.
line 55, column 10 of lib/widgets/action_section.dart: Expected to find '}'.
"""
    errors = parse_format_errors(details)
    assert len(errors) == 2
    assert "action_section.dart" in errors[0]


def test_normalize_analyzer_errors_for_fingerprint_strips_temp_dirs() -> None:
    errors = (
        "line 15, column 3 of c:/Users/x/AppData/Local/Temp/figma-flutter-spec23-abc123/"
        "analyze_check/lib/widgets/group_widget.dart: Getters, setters and methods can't be declared to be 'const'.",
        "line 15, column 3 of c:/Users/x/AppData/Local/Temp/figma-flutter-spec23-xyz789/"
        "analyze_check/lib/widgets/group_widget.dart: Getters, setters and methods can't be declared to be 'const'.",
    )
    normalized = normalize_analyzer_errors_for_fingerprint(errors)
    assert normalized[0] == normalized[1]
    assert "figma-flutter-spec23" not in normalized[0]
    assert "group_widget.dart" in normalized[0]


def test_parse_format_failed_paths_extracts_lib_relative_paths() -> None:
    from figma_flutter_agent.generator.validation import parse_format_failed_paths

    details = (
        "Could not format because the source could not be parsed:\n\n"
        "line 12, column 5 of C:/Temp/figma-flutter-spec23-abc/analyze_check/"
        "lib/features/sign_in/sign_in_screen.dart: Expected to find ','.\n"
    )
    paths = parse_format_failed_paths(details)
    assert paths == ("lib/features/sign_in/sign_in_screen.dart",)


def test_strip_inline_widget_duplicates_from_screens() -> None:
    planned = {
        "lib/features/demo/demo_screen.dart": (
            "import 'package:flutter/material.dart';\n"
            "class DemoScreen extends StatelessWidget {\n"
            "  const DemoScreen({super.key});\n"
            "  @override\n"
            "  Widget build(BuildContext context) => const GroupWidget();\n"
            "}\n"
            "class GroupWidget extends StatelessWidget {\n"
            "  const GroupWidget({super.key});\n"
            "  @override\n"
            "  Widget build(BuildContext context) => const SizedBox.shrink();\n"
            "}\n"
        ),
        "lib/widgets/group_widget.dart": (
            "import 'package:flutter/material.dart';\n"
            "import 'package:flutter_svg/flutter_svg.dart';\n"
            "class GroupWidget extends StatelessWidget {\n"
            "  const GroupWidget({super.key});\n"
            "  @override\n"
            "  Widget build(BuildContext context) {\n"
            "    return SvgPicture.asset('assets/icons/a.svg');\n"
            "  }\n"
            "}\n"
        ),
    }
    updated = strip_inline_widget_duplicates_from_screens(planned)
    screen = updated["lib/features/demo/demo_screen.dart"]
    assert "class GroupWidget extends" not in screen
    assert "const GroupWidget()" in screen
    assert "SvgPicture.asset" in updated["lib/widgets/group_widget.dart"]
    with_imports = ensure_referenced_widget_imports(updated)
    assert "widgets/group_widget.dart" in with_imports["lib/features/demo/demo_screen.dart"]


def test_collect_analyze_error_lines_prefers_analyzer_then_format() -> None:
    analyze_output = "error - lib/main.dart:1:1 - Undefined name 'x'."
    assert collect_analyze_error_lines(analyze_output, detail="dart analyze failed")[0].startswith(
        "error -"
    )

    format_output = (
        "Could not format because the source could not be parsed:\n\n"
        "line 1, column 1 of lib/main.dart: Expected to find ';'."
    )
    errors = collect_analyze_error_lines(format_output, detail="dart format failed")
    assert errors[0].startswith("line 1,")
