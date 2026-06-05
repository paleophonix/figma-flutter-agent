import time

from figma_flutter_agent.generator.dart.postprocess import (
    sanitize_named_only_widget_calls,
    strip_const_runtime_text_scaler,
)
from figma_flutter_agent.generator.planned_dart import sync_widget_class_constructors


def test_strip_const_runtime_text_scaler_removes_const_before_text() -> None:
    source = """
    return const Text(
      'LOG IN',
      textScaler: MediaQuery.textScalerOf(context),
    );
    """
    fixed = strip_const_runtime_text_scaler(source)
    assert "const Text(" not in fixed
    assert "MediaQuery.textScalerOf(context)" in fixed


def test_sanitize_named_only_widget_calls_drops_positional_junk() -> None:
    source = "SocialSignInButton([], [], [], []);"
    fixed = sanitize_named_only_widget_calls(
        source,
        widget_names=("SocialSignInButton",),
    )
    assert "SocialSignInButton(onPressed: () {})" in fixed
    assert "[]" not in fixed


def test_sync_widget_class_constructors_repairs_mangled_on_pressed_with_braces() -> None:
    source = """
class SocialButton extends StatelessWidget {
  final VoidCallback onPressed;
  const SocialButton(onPressed: () {}, {super.key, required this.onPressed}) {}, {super.key, required this.onPressed}) {}, {
    required this.text,
  });
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    fixed = sync_widget_class_constructors(source)
    assert fixed.count("const SocialButton(") == 1
    assert "const SocialButton({super.key, required this.onPressed});" in fixed
    assert ": super(key: key)" not in fixed
    assert "onPressed: () {}" not in fixed
    assert ") {}" not in fixed


def test_sync_widget_class_constructors_dedupes_super_key_and_required_key() -> None:
    source = """
class SocialSignInButton extends StatelessWidget {
  final VoidCallback onPressed;
  const SocialSignInButton({
    super.key,
    required Key key,
    required this.onPressed,
  });
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    fixed = sync_widget_class_constructors(source)
    assert "required Key key" not in fixed
    assert "super.key" in fixed
    assert fixed.count("super.key") == 1


def test_sync_widget_class_constructors_repairs_nested_duplicate_param_blocks() -> None:
    source = """
class CustomInputField extends StatelessWidget {
  final TextEditingController controller;
  const CustomInputField({required Key key, required this.controller, {required Key key, required this.controller, {super.key, required this.controller, {
  });
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    fixed = sync_widget_class_constructors(source)
    assert fixed.count("const CustomInputField(") == 1
    assert "required Key key" not in fixed
    assert "super.key" in fixed


def test_sync_widget_class_constructors_skips_huge_mangled_param_list() -> None:
    junk = "x" * 3000 + "{" * 400
    source = f"""
class Foo extends StatelessWidget {{
  const Foo({junk});
  @override
  Widget build(BuildContext context) => const SizedBox();
}}
"""
    started = time.monotonic()
    sync_widget_class_constructors(source)
    assert time.monotonic() - started < 2.0


def test_sync_widget_class_constructors_wraps_bare_on_pressed_params() -> None:
    source = """
class SocialSignInButton extends StatelessWidget {
  final VoidCallback onPressed;
  const SocialSignInButton(Key? key, void onPressed: () {});
  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    fixed = sync_widget_class_constructors(source)
    assert "const SocialSignInButton({" in fixed
    assert "required this.onPressed" in fixed
    assert "void onPressed:" not in fixed


def test_repair_obsolete_dart_default_colons_fixes_this_field() -> None:
    from figma_flutter_agent.generator.dart.postprocess import repair_obsolete_dart_default_colons

    source = "const Foo({this.text : 'Continue with Google'});"
    fixed = repair_obsolete_dart_default_colons(source)
    assert "this.text = 'Continue with Google'" in fixed
    assert "this.text :" not in fixed
