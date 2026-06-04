import 'dart:convert';
import 'dart:io';

import 'package:dart_ast_sidecar/rules.dart';

Future<void> main(List<String> args) async {
  final stdinText = await stdin.transform(utf8.decoder).join();
  Map<String, dynamic> request;
  try {
    request = jsonDecode(stdinText) as Map<String, dynamic>;
  } catch (e) {
    _emit(ok: false, errors: ['invalid_json: $e']);
    return;
  }
  final command = request['command'] as String? ?? '';
  final source = request['source'] as String? ?? '';
  try {
    switch (command) {
      case 'apply_rules':
        await _handleApplyRules(request, source);
      case 'extract_widget':
        await _handleExtractWidget(request, source);
      case 'replace_widget':
        await _handleReplaceWidget(request, source);
      case 'ensure_named_widgets_on_pressed':
        await _handleEnsureNamedWidgetsOnPressed(request, source);
      case 'wrap_widget_on_pressed':
        await _handleWrapWidgetOnPressed(request, source);
      case 'list_bindings':
        _handleListBindings(source);
      default:
        _emit(ok: false, errors: ['unsupported_command: $command']);
    }
  } catch (e) {
    _emit(ok: false, errors: ['command_failed: $e']);
  }
}

Future<void> _handleApplyRules(
  Map<String, dynamic> request,
  String source,
) async {
  final rules = (request['rules'] as List<dynamic>? ?? const <dynamic>[])
      .map((e) => e.toString())
      .toList();
  final options = request['options'] as Map<String, dynamic>? ?? const {};
  final includeTextScaler = options['includeTextScaler'] == true;
  final result = applyRules(
    source,
    rules: rules,
    includeTextScaler: includeTextScaler,
  );
  _emit(
    ok: true,
    source: result.source,
    edits: result.edits,
  );
}

Future<void> _handleExtractWidget(
  Map<String, dynamic> request,
  String source,
) async {
  final figmaId = request['figmaId'] as String? ?? '';
  final snippet = extractWidgetByFigmaKey(source, figmaId);
  if (snippet == null) {
    _emit(ok: false, errors: ['widget_not_found']);
    return;
  }
  _emit(ok: true, snippet: snippet);
}

Future<void> _handleEnsureNamedWidgetsOnPressed(
  Map<String, dynamic> request,
  String source,
) async {
  final names = (request['widgetNames'] as List<dynamic>? ?? const <dynamic>[])
      .map((e) => e.toString())
      .toList();
  final updated = ensureNamedWidgetsHaveOnPressed(source, names);
  _emit(ok: true, source: updated);
}

Future<void> _handleWrapWidgetOnPressed(
  Map<String, dynamic> request,
  String source,
) async {
  final widgetName = request['widgetName'] as String? ?? '';
  if (widgetName.isEmpty) {
    _emit(ok: false, errors: ['missing_widget_name']);
    return;
  }
  final updated = wrapWidgetOnPressedWithGestureDetector(source, widgetName);
  _emit(ok: true, source: updated);
}

void _handleListBindings(String source) {
  final bindings = listBindings(source)
      .map((record) => record.toJson())
      .toList();
  _emit(ok: true, bindings: bindings);
}

Future<void> _handleReplaceWidget(
  Map<String, dynamic> request,
  String source,
) async {
  final figmaId = request['figmaId'] as String? ?? '';
  final replacement = request['replacement'] as String? ?? '';
  final updated = replaceWidgetByFigmaKey(source, figmaId, replacement);
  if (updated == null) {
    _emit(ok: false, errors: ['widget_not_found']);
    return;
  }
  _emit(ok: true, source: updated);
}

void _emit({
  required bool ok,
  String? source,
  String? snippet,
  List<Map<String, dynamic>>? edits,
  List<String>? errors,
  List<Map<String, Object?>>? bindings,
}) {
  stdout.writeln(
    jsonEncode({
      'ok': ok,
      if (source != null) 'source': source,
      if (snippet != null) 'snippet': snippet,
      if (edits != null) 'edits': edits,
      if (errors != null) 'errors': errors,
      if (bindings != null) 'bindings': bindings,
    }),
  );
}
