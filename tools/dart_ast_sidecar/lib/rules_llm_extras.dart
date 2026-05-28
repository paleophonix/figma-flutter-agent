import 'rules_delimiters.dart';

const _validFontWeights = <int>{100, 200, 300, 400, 500, 600, 700, 800, 900};

final _dartMathMinRe = RegExp(r'(?<!math\.)(?<![.\w])min\s*\(');
final _dartMathMaxRe = RegExp(r'(?<!math\.)(?<![.\w])max\s*\(');
final _fontWeightRe = RegExp(r'FontWeight\.w(\d+)');
final _timerUsageRe = RegExp(r'\bTimer(?:\?|[\.(\s]|;|$)');

const _invalidLlmNamedParams = <String>[
  'failOverErrorResolvers',
  'failOnError',
];

String applyLlmExtras(String source) {
  var updated = source;
  updated = fixAnimatedCrossFadeParams(updated);
  updated = fixSliderThemePressedThumbRadius(updated);
  updated = fixSliderComponentShapePaintSignatures(updated);
  updated = fixDartMathMinMaxCalls(updated);
  updated = fixInvalidFontWeights(updated);
  updated = fixDartAsyncTimerUsage(updated);
  for (final param in _invalidLlmNamedParams) {
    updated = stripNamedParameter(updated, param);
  }
  return updated;
}

String fixAnimatedCrossFadeParams(String source) {
  const token = 'AnimatedCrossFade';
  final parts = <String>[];
  var index = 0;
  while (true) {
    final start = source.indexOf(token, index);
    if (start == -1) {
      parts.add(source.substring(index));
      break;
    }
    parts.add(source.substring(index, start));
    final parenStart = source.indexOf('(', start);
    if (parenStart == -1) {
      parts.add(source.substring(start));
      break;
    }
    final parenEnd = findMatchingParen(source, parenStart);
    if (parenEnd == null) {
      parts.add(source.substring(start));
      break;
    }
    var block = source.substring(start, parenEnd + 1);
    block = block.replaceAll(RegExp(r'\bfirst\s*:'), 'firstChild:');
    block = block.replaceAll(RegExp(r'\bsecond\s*:'), 'secondChild:');
    parts.add(block);
    index = parenEnd + 1;
  }
  return parts.join();
}

String fixSliderThemePressedThumbRadius(String source) {
  if (!source.contains('SliderThemeData') || !source.contains('pressedThumbRadius')) {
    return source;
  }
  const token = 'SliderThemeData';
  final parts = <String>[];
  var index = 0;
  while (true) {
    final start = source.indexOf(token, index);
    if (start == -1) {
      parts.add(source.substring(index));
      break;
    }
    parts.add(source.substring(index, start));
    final parenStart = source.indexOf('(', start);
    if (parenStart == -1) {
      parts.add(source.substring(start));
      break;
    }
    final parenEnd = findMatchingParen(source, parenStart);
    if (parenEnd == null) {
      parts.add(source.substring(start));
      break;
    }
    var block = source.substring(start, parenEnd + 1);
    if (!block.contains('thumbShape:')) {
      block = block.replaceAllMapped(
        RegExp(r'\bpressedThumbRadius\s*:\s*([^,\n)]+)\s*,?'),
        (m) => 'thumbShape: RoundSliderThumbShape(pressedThumbRadius: ${m.group(1)}),',
      );
    } else {
      block = block.replaceAll(
        RegExp(r'\bpressedThumbRadius\s*:\s*[^,\n)]+\s*,?\s*'),
        '',
      );
    }
    parts.add(block);
    index = parenEnd + 1;
  }
  return parts.join();
}

String fixSliderComponentShapePaintSignatures(String source) {
  if (!source.contains('SliderComponentShape') &&
      !source.contains('RoundSliderThumbShape') &&
      !source.contains('SliderThemeData') &&
      !source.contains('ThumbShape')) {
    return source;
  }
  var updated = source.replaceAll('LabelPainter', 'TextPainter');
  if (!updated.contains('isHorizontal')) {
    return updated;
  }
  return updated.replaceAll(RegExp(r'\bisHorizontal\b'), 'isDiscrete');
}

int _snapFontWeight(int value) {
  final snapped = (value / 100).round() * 100;
  return snapped.clamp(100, 900);
}

String fixInvalidFontWeights(String source) {
  return source.replaceAllMapped(_fontWeightRe, (match) {
    final value = int.parse(match.group(1)!);
    if (_validFontWeights.contains(value)) {
      return match.group(0)!;
    }
    return 'FontWeight.w${_snapFontWeight(value)}';
  });
}

String fixDartMathMinMaxCalls(String source) {
  final needsMin = _dartMathMinRe.hasMatch(source);
  final needsMax = _dartMathMaxRe.hasMatch(source);
  final needsMathPrefix = RegExp(r'\bmath\.').hasMatch(source);
  if (!needsMin && !needsMax && !needsMathPrefix) {
    return source;
  }
  var updated = source;
  if (needsMin) {
    updated = updated.replaceAll(_dartMathMinRe, 'math.min(');
  }
  if (needsMax) {
    updated = updated.replaceAll(_dartMathMaxRe, 'math.max(');
  }
  return insertDartLibraryImport(updated, 'dart:math', alias: 'math');
}

String fixDartAsyncTimerUsage(String source) {
  if (!_timerUsageRe.hasMatch(source)) {
    return source;
  }
  return insertDartLibraryImport(source, 'dart:async');
}

String insertDartLibraryImport(
  String source,
  String library, {
  String? alias,
}) {
  final importLine = alias == null
      ? "import '$library';"
      : "import '$library' as $alias;";
  if (source.contains(importLine)) {
    return source;
  }
  const material = "import 'package:flutter/material.dart';";
  if (source.contains(material)) {
    return source.replaceFirst(material, '$material\n$importLine');
  }
  final match = RegExp(r'^import .+;\s*$', multiLine: true).firstMatch(source);
  if (match == null) {
    return '$importLine\n\n$source';
  }
  final insertAt = match.end;
  return '${source.substring(0, insertAt)}\n$importLine${source.substring(insertAt)}';
}

String stripNamedParameter(String source, String paramName) {
  final token = '$paramName:';
  var updated = source;
  while (true) {
    final index = updated.indexOf(token);
    if (index == -1) {
      return updated;
    }
    var start = index;
    while (start > 0 && updated[start - 1].trim().isEmpty) {
      start--;
    }
    if (start > 0 && updated[start - 1] == ',') {
      start--;
    }
    final valueStart = index + token.length;
    final valueEnd = findExpressionEnd(updated, valueStart);
    if (valueEnd == null) {
      return updated;
    }
    var end = valueEnd;
    while (end < updated.length && updated[end].trim().isEmpty) {
      end++;
    }
    if (end < updated.length && updated[end] == ',') {
      end++;
    }
    updated = updated.substring(0, start) + updated.substring(end);
  }
}
