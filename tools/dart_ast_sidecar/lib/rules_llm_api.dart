import 'rules_delimiters.dart'
    show
        findExpressionEnd,
        findMatchingParen,
        findNamedParamValueStartInCall;
import 'rules_llm_extras.dart' show applyLlmExtras;

const _gestureParamFixes = <String, String>{
  'horizontalDragStart': 'onHorizontalDragStart',
  'horizontalDragUpdate': 'onHorizontalDragUpdate',
  'horizontalDragEnd': 'onHorizontalDragEnd',
  'verticalDragStart': 'onVerticalDragStart',
  'verticalDragUpdate': 'onVerticalDragUpdate',
  'verticalDragEnd': 'onVerticalDragEnd',
  'panStart': 'onPanStart',
  'panUpdate': 'onPanUpdate',
  'panEnd': 'onPanEnd',
};

const _iconGetterReplacements = <String, String>{
  'forward_15_rounded': 'forward_10',
  'replay_15_rounded': 'replay_10',
  'forward_15': 'forward_10',
  'replay_15': 'replay_10',
};

const _alignWidgetReplacements = <String, String>{
  'start': 'AlignmentDirectional.centerStart',
  'end': 'AlignmentDirectional.centerEnd',
  'topStart': 'AlignmentDirectional.topStart',
  'topEnd': 'AlignmentDirectional.topEnd',
  'bottomStart': 'AlignmentDirectional.bottomStart',
  'bottomEnd': 'AlignmentDirectional.bottomEnd',
  'centerStart': 'AlignmentDirectional.centerStart',
  'centerEnd': 'AlignmentDirectional.centerEnd',
  'center': 'Alignment.center',
  'left': 'Alignment.centerLeft',
  'right': 'Alignment.centerRight',
};

const _crossAxisReplacements = <String, String>{
  'start': 'CrossAxisAlignment.start',
  'end': 'CrossAxisAlignment.end',
  'center': 'CrossAxisAlignment.center',
  'stretch': 'CrossAxisAlignment.stretch',
  'topStart': 'CrossAxisAlignment.start',
  'topEnd': 'CrossAxisAlignment.end',
  'bottomStart': 'CrossAxisAlignment.start',
  'bottomEnd': 'CrossAxisAlignment.end',
  'centerStart': 'CrossAxisAlignment.start',
  'centerEnd': 'CrossAxisAlignment.end',
  'left': 'CrossAxisAlignment.start',
  'right': 'CrossAxisAlignment.end',
};

const _mainAxisReplacements = <String, String>{
  'start': 'MainAxisAlignment.start',
  'end': 'MainAxisAlignment.end',
  'center': 'MainAxisAlignment.center',
  'spaceBetween': 'MainAxisAlignment.spaceBetween',
  'spaceAround': 'MainAxisAlignment.spaceAround',
  'spaceEvenly': 'MainAxisAlignment.spaceEvenly',
  'topStart': 'MainAxisAlignment.start',
  'topEnd': 'MainAxisAlignment.end',
  'bottomStart': 'MainAxisAlignment.start',
  'bottomEnd': 'MainAxisAlignment.end',
  'centerStart': 'MainAxisAlignment.start',
  'centerEnd': 'MainAxisAlignment.end',
  'left': 'MainAxisAlignment.start',
  'right': 'MainAxisAlignment.end',
};

const _buttonWidgets = <String>[
  'ElevatedButton',
  'TextButton',
  'FilledButton',
  'OutlinedButton',
  'IconButton',
];

const _onPressedNonButtonWidgets = <String>[
  'Material',
  'Container',
  'SizedBox',
  'Padding',
  'Align',
  'Center',
  'ClipOval',
  'DecoratedBox',
  'CircleAvatar',
  'Icon',
];

final _misusedAlignmentParamRe = RegExp(
  r'(alignment|crossAxisAlignment|mainAxisAlignment)\s*:\s*Alignment\.'
  r'(start|end|center|stretch|spaceBetween|spaceAround|spaceEvenly|'
  r'topStart|topEnd|bottomStart|bottomEnd|centerStart|centerEnd|left|right)',
);
final _invalidAlignmentRe = RegExp(
  r'\bAlignment\.(start|end|topStart|topEnd|bottomStart|bottomEnd|'
  r'centerStart|centerEnd|left|right|center)\b',
);
final _misusedTextAlignRe = RegExp(
  r'textAlign:\s*(?!(?:TextAlign\.))(Center|Left|Right|Start|End|Justify)\b',
);
final _misusedTransformOriginRe = RegExp(r'origin:\s*Alignment\.(\w+)');
final _malformedEmptyClosureRe = RegExp(r'\(\)\s*\{,');
final _noopGestureWrapperRe = RegExp(
  r'GestureDetector\(\s*onTap:\s*\(\)\s*(?:\{[^}]*\})?\s*,\s*child:\s*',
  dotAll: true,
);

String fixAlignmentLiterals(String source) {
  var updated = source;
  updated = updated.replaceAllMapped(_misusedAlignmentParamRe, (match) {
    final param = match.group(1)!;
    final member = match.group(2)!;
    String? replacement;
    if (param == 'alignment') {
      replacement = _alignWidgetReplacements[member];
    } else if (param == 'crossAxisAlignment') {
      replacement = _crossAxisReplacements[member];
    } else {
      replacement = _mainAxisReplacements[member];
    }
    return replacement == null ? match.group(0)! : '$param: $replacement';
  });
  return updated.replaceAllMapped(_invalidAlignmentRe, (match) {
    final member = match.group(1)!;
    return _alignWidgetReplacements[member] ?? match.group(0)!;
  });
}

String fixMisusedFlexAlignmentParam(String source) {
  var updated = source;
  for (final flex in const ['Row', 'Column', 'Flex']) {
    updated = _replaceDirectNamedParam(updated, flex, 'alignment', 'mainAxisAlignment');
  }
  return updated;
}

String fixLlmDartApiMistakes(String source) {
  var updated = fixAlignmentLiterals(source);
  updated = fixMisusedFlexAlignmentParam(updated);
  for (final entry in _gestureParamFixes.entries) {
    updated = updated.replaceAll(
      RegExp('\\b${RegExp.escape(entry.key)}\\s*:'),
      '${entry.value}:',
    );
  }
  for (final entry in _iconGetterReplacements.entries) {
    updated = updated.replaceAll('Icons.${entry.key}', 'Icons.${entry.value}');
  }
  updated = updated.replaceAllMapped(_misusedTextAlignRe, (match) {
    final align = match.group(1)!.toLowerCase();
    return 'textAlign: TextAlign.$align';
  });
  updated = updated.replaceAllMapped(
    _misusedTransformOriginRe,
    (match) => 'alignment: Alignment.${match.group(1)}',
  );
  updated = updated.replaceAllMapped(_malformedEmptyClosureRe, (_) => '() {},');
  for (final widget in const ['GestureDetector', 'InkWell', 'InkResponse']) {
    updated = _replaceDirectNamedParam(updated, widget, 'onPressed', 'onTap');
  }
  for (final widget in _onPressedNonButtonWidgets) {
    updated = wrapWidgetOnPressedWithGestureDetector(updated, widget);
  }
  for (final widget in _buttonWidgets) {
    updated = _ensureWidgetHasOnPressed(updated, widget);
  }
  updated = _wrapBareInkWellWithMaterial(updated);
  updated = _ensureOutlinedButtonOpaqueFill(updated);
  updated = _ensureBorderedBoxDecorationFill(updated);
  updated = applyLlmExtras(updated);
  return updated;
}

/// Inject ``onPressed: () {}`` for custom widget constructors that require it.
String ensureNamedWidgetsHaveOnPressed(String source, List<String> widgetNames) {
  var updated = source;
  for (final name in widgetNames) {
    updated = _ensureWidgetHasOnPressed(updated, name);
  }
  return updated;
}

/// Move ``onPressed`` from [widgetName](...) onto a wrapping ``GestureDetector``.
String wrapWidgetOnPressedWithGestureDetector(String source, String widgetName) {
  final parts = <String>[];
  var index = 0;
  final opener = RegExp('(?<![A-Za-z0-9_])${RegExp.escape(widgetName)}\\(');
  while (true) {
    final match = opener.firstMatch(source.substring(index));
    if (match == null) {
      parts.add(source.substring(index));
      break;
    }
    final start = index + match.start;
    parts.add(source.substring(index, start));
    final parenStart = index + match.end - 1;
    final parenEnd = findMatchingParen(source, parenStart);
    if (parenEnd == null) {
      parts.add(source.substring(start));
      break;
    }
    final block = source.substring(start, parenEnd + 1);
    if (!block.contains('onPressed:')) {
      parts.add(block);
      index = parenEnd + 1;
      continue;
    }
    final callback = _extractNamedArgumentValue(block, 'onPressed');
    if (callback == null) {
      parts.add(block);
      index = parenEnd + 1;
      continue;
    }
    final cleaned = _stripNamedArgument(block, 'onPressed');
    parts.add('GestureDetector(onTap: $callback, child: $cleaned)');
    index = parenEnd + 1;
  }
  return parts.join();
}

String stripDesignCanvasGestureMatryoshka(String source) {
  var updated = source;
  while (true) {
    final collapsed = updated.replaceFirst(_noopGestureWrapperRe, '');
    if (collapsed == updated) {
      return updated;
    }
    updated = collapsed;
  }
}

String _replaceDirectNamedParam(
  String source,
  String widgetName,
  String oldParam,
  String newParam,
) {
  final parts = <String>[];
  var index = 0;
  final opener = RegExp('(?<![A-Za-z0-9_])${RegExp.escape(widgetName)}\\(');
  while (true) {
    final match = opener.firstMatch(source.substring(index));
    if (match == null) {
      parts.add(source.substring(index));
      break;
    }
    final start = index + match.start;
    parts.add(source.substring(index, start));
    final parenStart = index + match.end - 1;
    final parenEnd = findMatchingParen(source, parenStart);
    if (parenEnd == null) {
      parts.add(source.substring(start));
      break;
    }
    final inner = source.substring(parenStart + 1, parenEnd);
    parts.add('$widgetName(${_replaceTopLevelNamedParam(inner, oldParam, newParam)})');
    index = parenEnd + 1;
  }
  return parts.join();
}

String _replaceTopLevelNamedParam(String inner, String oldParam, String newParam) {
  final token = '$oldParam:';
  var depth = 0;
  var inString = false;
  var quote = '';
  var escape = false;
  for (var index = 0; index < inner.length; index++) {
    final char = inner[index];
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (char == r'\') {
        escape = true;
        continue;
      }
      if (char == quote) {
        inString = false;
      }
      continue;
    }
    if (char == "'" || char == '"') {
      inString = true;
      quote = char;
      continue;
    }
    if (char == '(' || char == '[' || char == '{') {
      depth++;
      continue;
    }
    if (char == ')' || char == ']' || char == '}') {
      depth--;
      continue;
    }
    if (depth == 0 && inner.startsWith(token, index)) {
      return '${inner.substring(0, index)}$newParam:${inner.substring(index + token.length)}';
    }
  }
  return inner;
}

String _ensureWidgetHasOnPressed(String source, String widgetName) {
  final parts = <String>[];
  var index = 0;
  final opener = RegExp('(?<![A-Za-z0-9_])${RegExp.escape(widgetName)}\\(');
  while (true) {
    final match = opener.firstMatch(source.substring(index));
    if (match == null) {
      parts.add(source.substring(index));
      break;
    }
    final start = index + match.start;
    parts.add(source.substring(index, start));
    final parenStart = index + match.end - 1;
    final parenEnd = findMatchingParen(source, parenStart);
    if (parenEnd == null) {
      parts.add(source.substring(start));
      break;
    }
    final block = source.substring(start, parenEnd + 1);
    final inner = block.substring(widgetName.length + 1, block.length - 1).trim();
    if (inner.startsWith('{')) {
      parts.add(block);
    } else if (RegExp(r'\bonPressed\s*:').hasMatch(block) ||
        RegExp(r'\bonTap\s*:').hasMatch(block)) {
      parts.add(block);
    } else if (inner.startsWith('[')) {
      parts.add('$widgetName(onPressed: () {}, child: Column(children: $inner))');
    } else if (RegExp(r'^\s*child\s*:').hasMatch(inner)) {
      parts.add('$widgetName(onPressed: () {}, $inner)');
    } else {
      parts.add(
        inner.isEmpty
            ? '$widgetName(onPressed: () {})'
            : '$widgetName(onPressed: () {}, child: $inner)',
      );
    }
    index = parenEnd + 1;
  }
  return parts.join();
}

String _wrapBareInkWellWithMaterial(String source) {
  var updated = source;
  var index = 0;
  while (true) {
    final start = updated.indexOf('InkWell(', index);
    if (start == -1) {
      return updated;
    }
    final parenStart = start + 'InkWell'.length;
    final parenEnd = findMatchingParen(updated, parenStart);
    if (parenEnd == null) {
      return updated;
    }
    final block = updated.substring(start, parenEnd + 1);
    if (RegExp(r'\bMaterial\s*\(').hasMatch(updated.substring(0, start))) {
      index = parenEnd + 1;
      continue;
    }
    final wrapped =
        'Material(color: Colors.transparent, clipBehavior: Clip.antiAlias, child: $block)';
    updated = updated.replaceRange(start, parenEnd + 1, wrapped);
    index = start + wrapped.length;
  }
}

String _ensureOutlinedButtonOpaqueFill(String source) {
  var updated = source;
  var index = 0;
  const token = 'OutlinedButton.styleFrom';
  while (true) {
    final start = updated.indexOf(token, index);
    if (start == -1) {
      return updated;
    }
    final parenOpen = start + token.length;
    final parenClose = findMatchingParen(updated, parenOpen);
    if (parenClose == null) {
      return updated;
    }
    final block = updated.substring(start, parenClose + 1);
    index = parenClose + 1;
    if (block.contains('backgroundColor:')) {
      continue;
    }
    if (!block.contains('side:') && !block.contains('BorderSide')) {
      continue;
    }
    final inner = block.substring(block.indexOf('(') + 1, block.lastIndexOf(')'));
    final innerStripped = inner.trimLeft();
    const fill = 'backgroundColor: const Color(0xFFFFFFFF)';
    final patchedInner = innerStripped.isEmpty ? fill : '$fill, $innerStripped';
    final patched = 'OutlinedButton.styleFrom($patchedInner)';
    updated = updated.replaceRange(start, parenClose + 1, patched);
    index = start + patched.length;
  }
}

String _ensureBorderedBoxDecorationFill(String source) {
  var updated = source;
  var index = 0;
  while (true) {
    final start = updated.indexOf('BoxDecoration(', index);
    if (start == -1) {
      return updated;
    }
    final parenOpen = start + 'BoxDecoration'.length;
    final parenClose = findMatchingParen(updated, parenOpen);
    if (parenClose == null) {
      return updated;
    }
    final block = updated.substring(start, parenClose + 1);
    index = parenClose + 1;
    if (!_boxDecorationNeedsFill(block)) {
      continue;
    }
    final inner = block.substring(block.indexOf('(') + 1, block.lastIndexOf(')'));
    final innerStripped = inner.trimLeft();
    const fill = 'color: const Color(0xFFFFFFFF)';
    final patchedInner = innerStripped.isEmpty ? fill : '$fill, $innerStripped';
    final patched = 'BoxDecoration($patchedInner)';
    updated = updated.replaceRange(start, parenClose + 1, patched);
    index = start + patched.length;
  }
}

String _stripTopLevelBorderField(String inner) {
  final match = RegExp(r'\bborder\s*:\s*Border\.all\s*\(').firstMatch(inner);
  if (match == null) {
    return inner;
  }
  final parenOpen = match.end - 1;
  final parenClose = findMatchingParen(inner, parenOpen);
  if (parenClose == null) {
    return inner;
  }
  var end = parenClose + 1;
  while (end < inner.length && ' \t\n\r'.contains(inner[end])) {
    end++;
  }
  if (end < inner.length && inner[end] == ',') {
    end++;
  }
  var start = match.start;
  while (start > 0 && ' \t\n\r'.contains(inner[start - 1])) {
    start--;
  }
  if (start > 0 && inner[start - 1] == ',') {
    start--;
  }
  return inner.substring(0, start) + inner.substring(end);
}

bool _boxDecorationNeedsFill(String block) {
  if (!RegExp(r'\bborder\s*:').hasMatch(block)) {
    return false;
  }
  final inner = block.substring(block.indexOf('(') + 1, block.lastIndexOf(')'));
  final withoutBorder = _stripTopLevelBorderField(inner);
  if (RegExp(r'\bgradient\s*:').hasMatch(withoutBorder)) {
    return false;
  }
  if (RegExp(r'\bcolor\s*:').hasMatch(withoutBorder)) {
    return false;
  }
  return true;
}

String? _extractNamedArgumentValue(String block, String paramName) {
  final valueStart = findNamedParamValueStartInCall(block, paramName);
  if (valueStart == null) {
    return null;
  }
  final valueEnd = findExpressionEnd(block, valueStart);
  if (valueEnd == null || valueEnd <= valueStart) {
    return null;
  }
  return block.substring(valueStart, valueEnd).trim();
}

String _stripNamedArgument(String block, String paramName) {
  final token = '$paramName:';
  final valueStart = findNamedParamValueStartInCall(block, paramName);
  if (valueStart == null) {
    return block;
  }
  var index = valueStart;
  while (index > 0 && block[index - 1].trim().isEmpty) {
    index--;
  }
  index -= token.length;
  if (index < 0 || !block.startsWith(token, index)) {
    return block;
  }
  final valueEnd = findExpressionEnd(block, valueStart);
  if (valueEnd == null || valueEnd <= valueStart) {
    return block;
  }
  var trailing = valueEnd;
  while (trailing < block.length && block[trailing].trim().isEmpty) {
    trailing++;
  }
  if (trailing < block.length && block[trailing] == ',') {
    trailing++;
  }
  return block.substring(0, index) + block.substring(trailing);
}
