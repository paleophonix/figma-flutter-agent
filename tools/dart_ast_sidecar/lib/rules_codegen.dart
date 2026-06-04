import 'rules_flex_wrap.dart';
import 'rules_imports.dart';
import 'rules_layout_strip.dart';
import 'rules_layout_unscale.dart';
import 'rules_llm_api.dart';
import 'rules_strings.dart';
import 'rules_syntax_repairs.dart';
import 'rules_text_scaler.dart';

/// Full deterministic codegen pass (mirrors legacy ``dart_postprocess`` pipeline).
ApplyCodegenResult applyCodegenPass(
  String source, {
  bool includeTextScaler = false,
}) {
  var updated = source;
  final edits = <Map<String, dynamic>>[];

  void mark(String rule, String before) {
    if (updated != before) {
      edits.add({'rule': rule});
    }
  }

  var before = updated;
  updated = stripBareUnicodeEscapesOutsideLiterals(updated);
  mark('strip_bare_unicode_escapes', before);

  before = updated;
  updated = normalizeLlmDartStringEscapes(updated);
  mark('normalize_string_literals', before);

  before = updated;
  updated = sanitizeImportsPass(updated);
  updated = ensureAppColorsImport(updated);
  updated = ensureAppLayoutImport(updated);
  mark('sanitize_imports', before);

  before = updated;
  updated = unscaleDesignExpressions(updated);
  mark('unscale_design_expressions', before);

  before = updated;
  updated = stripResponsiveLayoutBuilder(updated);
  mark('unwrap_scale_layout_builder', before);

  before = updated;
  updated = stripViewportScaleHack(updated);
  mark('strip_viewport_scale_transform', before);

  before = updated;
  updated = fixLlmDartApiMistakes(updated);
  mark('fix_llm_api_mistakes', before);

  before = updated;
  updated = stripDesignCanvasGestureMatryoshka(updated);
  mark('strip_design_canvas_gesture_matryoshka', before);

  before = updated;
  updated = wrapFlexRowColumnChildren(updated);
  mark('wrap_flex_row_column_children', before);

  before = updated;
  updated = applyLlmSyntaxRepairs(updated);
  mark('llm_syntax_repairs', before);

  if (includeTextScaler) {
    before = updated;
    updated = ensureTextScalerSupport(updated);
    mark('ensure_text_scaler', before);
  }

  return ApplyCodegenResult(source: updated, edits: edits);
}

class ApplyCodegenResult {
  ApplyCodegenResult({required this.source, required this.edits});

  final String source;
  final List<Map<String, dynamic>> edits;
}
