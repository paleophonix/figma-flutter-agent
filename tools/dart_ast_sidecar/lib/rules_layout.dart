import 'rules_codegen.dart';
import 'rules_imports.dart';
import 'rules_layout_strip.dart';
import 'rules_layout_unscale.dart';
import 'rules_llm_api.dart';
import 'rules_strings.dart';
import 'rules_text_scaler.dart';

class ApplyRulesResult {
  ApplyRulesResult({required this.source, required this.edits});

  final String source;
  final List<Map<String, dynamic>> edits;
}

ApplyRulesResult applyRules(
  String source, {
  required List<String> rules,
  bool includeTextScaler = false,
}) {
  if (rules.contains('codegen_pass')) {
    final result = applyCodegenPass(
      source,
      includeTextScaler: includeTextScaler,
    );
    return ApplyRulesResult(source: result.source, edits: result.edits);
  }

  var updated = source;
  final edits = <Map<String, dynamic>>[];

  for (final rule in rules) {
    final before = updated;
    switch (rule) {
      case 'strip_bare_unicode_escapes':
        updated = stripBareUnicodeEscapesOutsideLiterals(updated);
      case 'normalize_string_literals':
        updated = normalizeLlmDartStringEscapes(updated);
      case 'sanitize_imports':
        updated = sanitizeImportsPass(updated);
      case 'unscale_design_expressions':
        updated = unscaleDesignExpressions(updated);
      case 'unwrap_scale_layout_builder':
        updated = stripResponsiveLayoutBuilder(updated);
      case 'strip_viewport_scale_transform':
        updated = stripViewportScaleHack(updated);
      case 'fix_llm_api_mistakes':
        updated = fixLlmDartApiMistakes(updated);
      case 'fix_alignment_literals':
        updated = fixAlignmentLiterals(updated);
      case 'strip_design_canvas_gesture_matryoshka':
        updated = stripDesignCanvasGestureMatryoshka(updated);
      default:
        break;
    }
    if (updated != before) {
      edits.add({'rule': rule});
    }
  }
  if (includeTextScaler) {
    final before = updated;
    updated = ensureTextScalerSupport(updated);
    if (updated != before) {
      edits.add({'rule': 'ensure_text_scaler'});
    }
  }
  return ApplyRulesResult(source: updated, edits: edits);
}
