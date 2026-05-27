"""Tests for LLM Dart post-processing."""

import pytest

from figma_flutter_agent.generator.codegen_checks import validate_generated_dart
from figma_flutter_agent.generator.dart_postprocess import (
    discover_widgets_requiring_on_pressed,
    ensure_required_on_pressed_callbacks,
    ensure_text_scaler_support,
    fix_invalid_alignment_literals,
    fix_llm_dart_api_mistakes,
    fix_misused_text_align_widget,
    fix_misused_transform_origin_alignment,
    postprocess_generated_dart,
)
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_ensure_text_scaler_support_injects_build_declaration() -> None:
    source = """
class DayCircleSelector extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(children: [Text('SU')]);
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "Text('SU', textScaler: MediaQuery.textScalerOf(context))" in updated


def test_ensure_text_scaler_support_is_idempotent() -> None:
    source = """
class HomeScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Text('Home', textScaler: textScaler);
  }
}
"""
    assert ensure_text_scaler_support(source) == source


def test_ensure_text_scaler_support_handles_multiline_build_signature() -> None:
    source = """
class TimeScrollPicker extends StatelessWidget {
  @override
  Widget build(
    BuildContext context,
  ) {
    return ListView(children: [Text('11')]);
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "Text('11', textScaler: MediaQuery.textScalerOf(context))" in updated
    assert "),," not in updated


def test_ensure_text_scaler_support_handles_styled_text() -> None:
    source = """
class DayCircle extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Text(
      'SU',
      style: TextStyle(fontSize: 14.0),
    );
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "textScaler: MediaQuery.textScalerOf(context)" in updated
    assert "),," not in updated


def test_ensure_text_scaler_support_handles_non_context_parameter_name() -> None:
    source = """
class WeekdaySelector extends StatelessWidget {
  @override
  Widget build(BuildContext ctx) {
    return Text('M');
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "textScaler: MediaQuery.textScalerOf(ctx)" in updated


def test_ensure_text_scaler_support_handles_builder_callbacks() -> None:
    source = """
class TimePickerContainer extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemBuilder: (context, index) {
        return const Text('11');
      },
    );
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "const Text" not in updated
    assert "Text('11', textScaler: MediaQuery.textScalerOf(context))" in updated


def test_ensure_text_scaler_support_injects_into_helper_methods() -> None:
    source = """
class TimePickerContainer extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(children: [_buildPicker(context)]);
  }

  Widget _buildPicker(BuildContext context) {
    return Text('11');
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "Text('11', textScaler: MediaQuery.textScalerOf(context))" in updated


def test_ensure_text_scaler_support_strips_const_list_literals() -> None:
    source = """
class TimePickerWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(
      children: const [
        Text('11'),
        Text('12'),
      ],
    );
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "const [" not in updated
    assert "textScaler: MediaQuery.textScalerOf(context)" in updated


def test_ensure_text_scaler_support_strips_const_widget_wrappers() -> None:
    source = """
class TimePickerWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        Text('11'),
      ],
    );
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "return const Column" not in updated
    assert "return Column(" in updated
    assert "textScaler: MediaQuery.textScalerOf(context)" in updated


def test_fix_invalid_alignment_literals_rewrites_align_widget_start() -> None:
    source = """
class RemindersScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Align(alignment: Alignment.start, child: const SizedBox());
  }
}
"""
    updated = fix_invalid_alignment_literals(source)
    assert "Alignment.start" not in updated
    assert "AlignmentDirectional.centerStart" in updated


def test_fix_invalid_alignment_literals_rewrites_cross_axis_start() -> None:
    source = """
class RemindersScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: Alignment.start, children: const [SizedBox()]);
  }
}
"""
    updated = fix_invalid_alignment_literals(source)
    assert "crossAxisAlignment: CrossAxisAlignment.start" in updated
    assert "AlignmentDirectional" not in updated


def test_fix_invalid_alignment_literals_rewrites_main_axis_end() -> None:
    source = """
class RemindersScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(mainAxisAlignment: Alignment.end, children: const [SizedBox()]);
  }
}
"""
    updated = fix_invalid_alignment_literals(source)
    assert "mainAxisAlignment: MainAxisAlignment.end" in updated


def test_ensure_text_scaler_support_injects_build_declaration_for_helper_without_context() -> None:
    source = """
class MeditationTimePicker extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return _buildLabel();
  }

  Widget _buildLabel() {
    return Text('11');
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "_buildLabel(BuildContext context)" in updated
    assert "_buildLabel(context)" in updated
    assert "Text('11', textScaler: MediaQuery.textScalerOf(context))" in updated


def test_ensure_text_scaler_support_adds_context_to_helper_using_theme_of() -> None:
    source = """
class TimePickerWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return _buildWheel();
  }

  Widget _buildWheel() {
    return Text(
      '11',
      style: Theme.of(context).textTheme.headlineSmall,
    );
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "_buildWheel(BuildContext context)" in updated
    assert "_buildWheel(context)" in updated
    assert "Theme.of(context)" in updated
    assert "textScaler: MediaQuery.textScalerOf(context)" in updated


def test_ensure_text_scaler_support_handles_text_rich() -> None:
    source = """
class Demo extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Text.rich(TextSpan(text: 'Hi'));
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "textScaler: MediaQuery.textScalerOf(context)" in updated


def test_fix_llm_dart_api_mistakes_rewrites_gesture_detector_params() -> None:
    source = """
GestureDetector(
  horizontalDragUpdate: (_) {},
  child: const SizedBox(),
)
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "onHorizontalDragUpdate:" in updated
    assert "horizontalDragUpdate:" not in updated


def test_fix_misused_transform_origin_alignment_maps_to_alignment_param() -> None:
    source = "Transform.scale(scale: 1.0, origin: Alignment.center, child: child)"
    updated = fix_misused_transform_origin_alignment(source)
    assert "alignment: Alignment.center" in updated
    assert "origin: Alignment" not in updated


def test_fix_misused_text_align_widget_maps_center_to_enum() -> None:
    source = "Text('Hi', textAlign: Center, style: TextStyle())"
    updated = fix_misused_text_align_widget(source)
    assert "textAlign: TextAlign.center" in updated
    assert "textAlign: Center" not in updated


def test_fix_llm_dart_api_mistakes_rewrites_invalid_icons() -> None:
    source = """
Icon(Icons.forward_15_rounded)
Icon(Icons.replay_15_rounded)
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "Icons.forward_10" in updated
    assert "Icons.replay_10" in updated
    assert "forward_15" not in updated


def test_fix_llm_dart_api_mistakes_rewrites_animated_cross_fade_params() -> None:
    source = """
AnimatedCrossFade(
  first: const Icon(Icons.play_arrow),
  second: const Icon(Icons.pause),
  duration: const Duration(milliseconds: 200),
  crossFadeState: CrossFadeState.showFirst,
)
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "firstChild:" in updated
    assert "secondChild:" in updated
    assert " first:" not in updated
    assert " second:" not in updated


def test_fix_llm_dart_api_mistakes_moves_pressed_thumb_radius_to_thumb_shape() -> None:
    source = """
SliderTheme(
  data: SliderThemeData(
    trackHeight: 2,
    pressedThumbRadius: 12.0,
  ),
  child: Slider(value: 0.5, onChanged: (_) {}),
)
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "thumbShape: RoundSliderThumbShape(pressedThumbRadius: 12.0)" in updated
    assert "pressedThumbRadius:" not in updated.replace(
        "RoundSliderThumbShape(pressedThumbRadius: 12.0)", ""
    )


def test_fix_llm_dart_api_mistakes_adds_dart_math_import_for_min_calls() -> None:
    source = """
import 'package:flutter/material.dart';

class MusicV2Screen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final width = min(MediaQuery.sizeOf(context).width, 400.0);
    return SizedBox(width: width);
  }
}
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "import 'dart:math' as math;" in updated
    assert "math.min(" in updated
    assert "MainAxisSize.min" not in updated


def test_fix_llm_dart_api_mistakes_snaps_invalid_font_weight() -> None:
    source = """
const style = TextStyle(fontWeight: FontWeight.w750);
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "FontWeight.w750" not in updated
    assert "FontWeight.w800" in updated


def test_fix_llm_dart_api_mistakes_preserves_valid_font_weight() -> None:
    source = """
const style = TextStyle(fontWeight: FontWeight.w500);
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "FontWeight.w500" in updated


def test_fix_llm_dart_api_mistakes_adds_dart_async_import_for_timer() -> None:
    source = """
import 'package:flutter/material.dart';

class MusicV2Screen extends StatefulWidget {
  @override
  State<MusicV2Screen> createState() => _MusicV2ScreenState();
}

class _MusicV2ScreenState extends State<MusicV2Screen> {
  Timer? _progressTimer;

  void _startProgressTimer() {
    _progressTimer = Timer.periodic(const Duration(seconds: 1), (_) {});
  }

  @override
  Widget build(BuildContext context) => const SizedBox();
}
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "import 'dart:async';" in updated
    assert "Timer.periodic" in updated


def test_fix_llm_dart_api_mistakes_strips_fail_over_error_resolvers() -> None:
    source = """
SvgPicture.asset(
  'assets/icons/skip.svg',
  failOverErrorResolvers: const [],
  width: 39,
)
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "failOverErrorResolvers" not in updated
    assert "width: 39" in updated


def test_fix_llm_dart_api_mistakes_fixes_slider_thumb_shape_paint_signature() -> None:
    source = """
class CustomDoubleCircleThumbShape extends SliderComponentShape {
  @override
  void paint(
    PaintingContext context,
    Offset center, {
    required Animation<double> activationAnimation,
    required Animation<double> enableAnimation,
    required bool isHorizontal,
    required LabelPainter labelPainter,
    required RenderBox parentBox,
    required SliderThemeData sliderTheme,
    required TextDirection textDirection,
    required double value,
    required double textScaleFactor,
    required Size sizeWithOverflow,
  }) {}
}
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "LabelPainter" not in updated
    assert "TextPainter labelPainter" in updated
    assert "isDiscrete" in updated
    assert "isHorizontal" not in updated


def test_fix_llm_dart_api_mistakes_rewrites_on_pressed_on_ink_well() -> None:
    source = """
InkWell(
  onPressed: widget.onTap,
  child: const Icon(Icons.close),
)
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "onTap: widget.onTap" in updated
    assert "onPressed:" not in updated


def test_fix_llm_dart_api_mistakes_adds_dart_math_import_for_math_prefix() -> None:
    source = """
import 'package:flutter/material.dart';

class SkipIntervalButton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final size = math.max(39.0, 24.0);
    return SizedBox(width: size);
  }
}
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "import 'dart:math' as math;" in updated
    assert "math.max(" in updated


def test_fix_llm_dart_api_mistakes_wraps_material_on_pressed_in_gesture_detector() -> None:
    source = """
return Material(
  color: Colors.transparent,
  shape: const CircleBorder(),
  onPressed: widget.onTap,
  child: Icon(Icons.close),
);
"""
    updated = fix_llm_dart_api_mistakes(source)
    assert "GestureDetector(onTap: widget.onTap, child: Material(" in updated
    assert "onPressed:" not in updated


def test_ensure_text_scaler_support_fixes_nested_builder_text_scaler_reference() -> None:
    source = """
class SignInScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return ListView.builder(
      itemBuilder: (context, index) {
        return Text('SAVE', textScaler: textScaler);
      },
    );
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "Text('SAVE', textScaler: MediaQuery.textScalerOf(context))" in updated
    assert "textScaler: textScaler" not in updated
    assert "final textScaler = MediaQuery.textScalerOf(context);" not in updated


def test_strip_llm_responsive_layout_builder_unwraps_scaled_stack() -> None:
    from figma_flutter_agent.generator.dart_postprocess import (
        strip_llm_responsive_layout_builder,
    )

    source = """
    Stack(
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final double scaleX = constraints.maxWidth / designWidth;
            final double scaleY = constraints.maxHeight / designHeight;
            return SingleChildScrollView(
              child: SizedBox(
                width: constraints.maxWidth,
                height: designHeight * scaleY,
                child: Stack(
                  children: [
                    Positioned(
                      left: 20.0 * scaleX,
                      top: 100.0 * scaleY,
                      child: Text('Hi'),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
    """
    updated = strip_llm_responsive_layout_builder(source)
    assert "LayoutBuilder" not in updated
    assert "scaleX" not in updated
    assert "left: 20.0" in updated
    assert "top: 100.0" in updated


def test_strip_llm_viewport_scale_hack_removes_screen_scale_transform() -> None:
    from figma_flutter_agent.generator.dart_postprocess import strip_llm_viewport_scale_hack

    source = """
    Widget build(BuildContext context) {
      final double canvasWidth = 414.0;
      final double screenWidth = MediaQuery.of(context).size.width;
      final double screenScale = screenWidth / canvasWidth;
      return Center(
        child: Transform.scale(
          scale: screenScale,
          alignment: Alignment.topCenter,
          child: SizedBox(
            width: canvasWidth,
            height: 896.0,
            child: Text('Hi'),
          ),
        ),
      );
    }
    """
    updated = strip_llm_viewport_scale_hack(source)
    assert "Transform.scale" not in updated
    assert "screenScale" not in updated
    assert "child: SizedBox(" in updated


def test_fix_llm_dart_api_mistakes_strips_fail_on_error() -> None:
    source = """
    return Material(
      failOnError: true,
      child: Text('Go'),
    );
    """
    updated = fix_llm_dart_api_mistakes(source)
    assert "failOnError" not in updated


def test_ensure_text_scaler_support_fixes_out_of_scope_text_scaler_reference() -> None:
    source = """
class MusicV2Screen extends StatefulWidget {
  const MusicV2Screen({super.key});

  @override
  State<MusicV2Screen> createState() => _MusicV2ScreenState();
}

class _MusicV2ScreenState extends State<MusicV2Screen> {
  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Column(children: [_buildTitle(context)]);
  }

  Widget _buildTitle(BuildContext context) {
    return Text('Title', textScaler: textScaler);
  }
}
"""
    updated = ensure_text_scaler_support(source)
    assert "Text('Title', textScaler: MediaQuery.textScalerOf(context))" in updated
    assert "final textScaler = MediaQuery.textScalerOf(context);" not in updated


def test_wrap_on_pressed_skips_material_button_token() -> None:
    from figma_flutter_agent.generator.dart_postprocess import (
        _wrap_widget_on_pressed_with_gesture_detector,
    )

    source = """
    return MaterialButton(onPressed: () {}, child: Text('Go'));
    """
    updated = _wrap_widget_on_pressed_with_gesture_detector(source, "Material")
    assert updated == source


def test_postprocess_reverts_when_delimiters_break(monkeypatch: pytest.MonkeyPatch) -> None:
    source = "class DemoScreen extends StatelessWidget { Widget build(BuildContext c) => Text('x'); }"
    monkeypatch.setattr(
        "figma_flutter_agent.generator.llm_dart.validate_dart_delimiters",
        lambda _source: "Unexpected '}' near line 1",
    )
    updated = postprocess_generated_dart(source)
    assert updated == source


def test_postprocess_generated_dart_applies_alignment_and_text_scaler_fixes() -> None:
    source = """
class RemindersScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.start,
      child: Text('SAVE'),
    );
  }
}
"""
    updated = postprocess_generated_dart(source)
    assert "AlignmentDirectional.centerStart" in updated
    assert "textScaler: MediaQuery.textScalerOf(context)" in updated


def test_ensure_text_scaler_support_passes_codegen_validation() -> None:
    tree = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.CONTAINER)
    screen = ensure_text_scaler_support(
        """
class RemindersScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return GeneratedScreenShell(child: Column(children: [Text('SAVE')]));
  }
}
"""
    )
    widget = ensure_text_scaler_support(
        """
class DayCircleSelector extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Text('M');
  }
}
"""
    )
    validate_generated_dart(
        {
            "lib/features/reminders/reminders_screen.dart": screen,
            "lib/widgets/day_circle_selector.dart": widget,
        },
        tree,
        responsive_enabled=True,
        avoid_fixed_sizes=False,
    )


def test_discover_widgets_requiring_on_pressed() -> None:
    planned = {
        "lib/widgets/social_button.dart": """
class SocialButton extends StatelessWidget {
  const SocialButton({super.key, required this.onPressed, required this.label});
  final VoidCallback onPressed;
  final String label;
}
""",
        "lib/widgets/logo.dart": "class Logo extends StatelessWidget {}",
    }
    assert discover_widgets_requiring_on_pressed(planned) == ("SocialButton",)


def test_ensure_required_on_pressed_callbacks_for_custom_widget() -> None:
    screen = "child: SocialButton(label: 'GOOGLE'),"
    fixed = ensure_required_on_pressed_callbacks(
        screen,
        widget_names=("SocialButton",),
    )
    assert "onPressed: () {}" in fixed


def test_reconcile_injects_on_pressed_for_required_widget() -> None:
    planned = {
        "lib/features/auth/auth_screen.dart": "child: SocialButton(icon: Icon(Icons.add)),",
        "lib/widgets/social_button.dart": """
class SocialButton extends StatelessWidget {
  const SocialButton({super.key, required this.onPressed, this.icon});
  final VoidCallback onPressed;
  final Widget? icon;
}
""",
    }
    reconciled = reconcile_planned_dart_files(planned)
    assert "onPressed: () {}" in reconciled["lib/features/auth/auth_screen.dart"]
