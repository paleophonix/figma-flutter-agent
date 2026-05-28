import 'rules_delimiters.dart';

final _textScalerDeclRe = RegExp(
  r'(textScaler:\s*MediaQuery\.textScalerOf\(\w+\)|'
  r'(?:final|var)\s+\w*\s*textScaler\s*=\s*MediaQuery\.textScalerOf\(\w+\))',
);
final _buildContextParamRe = RegExp(r'BuildContext\s+(\w+)');
final _textWidgetRe = RegExp(
  r'(?<!TextStyle)(?<!TextSpan)\b(?:Text(?:\.rich)?|SelectableText|EditableText)\s*\(',
);
final _buildMethodRe = RegExp(
  r'Widget\s+build\s*\(\s*BuildContext\s+(\w+)[\s\S]*?\)\s*\{',
);
final _helperMethodSignatureRe = RegExp(
  r'(\w+)\s+(_\w+)\s*\(([^)]*)\)\s*(?:async\s*)?\{',
);
final _contextReferenceRe = RegExp(
  r'\b(?:Theme|MediaQuery|Navigator|Scaffold|DefaultTextStyle)\.of\(context\)'
  r'|\bMediaQuery\.textScalerOf\(context\)',
);
final _constBeforeTextRe = RegExp(r'\bconst\s*$');
final _textScalerDeclLineRe = RegExp(
  r'^[ \t]*(?:final|var)\s+textScaler\s*=\s*MediaQuery\.textScalerOf\([^)]+\);\s*\n?',
  multiLine: true,
);

const _runtimeTextScaler = 'textScaler: MediaQuery.textScalerOf(';

String ensureTextScalerSupport(String source) {
  var updated = ensureHelperMethodsHaveBuildContext(source);
  updated = fixOutOfScopeTextScalerReferences(updated);
  if (_textScalerDeclRe.hasMatch(updated) &&
      !textWidgetsMissingScaler(updated) &&
      !updated.contains('textScaler: textScaler')) {
    return removeUnusedTextScalerDeclarations(updated);
  }
  updated = attachTextScalerToTextWidgets(updated);
  updated = stripConstAroundRuntimeTextScaler(updated);
  if (_textWidgetRe.hasMatch(updated) && textWidgetsMissingScaler(updated)) {
    updated = injectBuildTextScalerDeclaration(updated);
    updated = attachTextScalerToTextWidgets(updated);
    updated = stripConstAroundRuntimeTextScaler(updated);
  }
  updated = fixOutOfScopeTextScalerReferences(updated);
  updated = ensureHelperMethodsHaveBuildContext(updated);
  if (!updated.contains('textScaler: textScaler')) {
    updated = removeUnusedTextScalerDeclarations(updated);
  }
  return updated;
}

String removeUnusedTextScalerDeclarations(String source) {
  if (source.contains('textScaler: textScaler')) {
    return source;
  }
  if (!_textScalerDeclLineRe.hasMatch(source)) {
    return source;
  }
  final stripped = source.replaceAll(_textScalerDeclLineRe, '');
  if (RegExp(r'(?<![.\w])textScaler\b(?!\s*:)').hasMatch(stripped)) {
    return source;
  }
  return stripped;
}

bool textScalerLocalInScope(String source, int index) {
  final braceOpen = findEnclosingBraceOpen(source, index);
  if (braceOpen == null) {
    return false;
  }
  final braceClose = findMatchingBracket(source, braceOpen, '{', '}');
  if (braceClose == null) {
    return false;
  }
  final body = source.substring(braceOpen, braceClose + 1);
  return RegExp(r'\b(?:final|var)\s+textScaler\s*=\s*MediaQuery\.textScalerOf\(')
      .hasMatch(body);
}

String fixOutOfScopeTextScalerReferences(String source) {
  final parts = <String>[];
  var index = 0;
  for (final match in _textWidgetRe.allMatches(source)) {
    final callStart = match.end - 1;
    final callEnd = findMatchingParen(source, callStart);
    if (callEnd == null) {
      continue;
    }
    final textStart = match.start;
    final fullCall = source.substring(textStart, callEnd + 1);
    if (!fullCall.contains('textScaler: textScaler')) {
      continue;
    }
    if (textScalerLocalInScope(source, textStart)) {
      continue;
    }
    final contextName = contextNameForPosition(source, textStart);
    if (contextName == null) {
      continue;
    }
    final fixedCall = fullCall.replaceAll(
      'textScaler: textScaler',
      'textScaler: MediaQuery.textScalerOf($contextName)',
    );
    parts.add(source.substring(index, textStart));
    parts.add(fixedCall);
    index = callEnd + 1;
  }
  if (parts.isEmpty) {
    return source;
  }
  parts.add(source.substring(index));
  return parts.join();
}

String injectBuildTextScalerDeclaration(String source) {
  final match = _buildMethodRe.firstMatch(source);
  if (match == null) {
    return source;
  }
  final contextName = match.group(1)!;
  final insertAt = match.end;
  final declaration = '\n    final textScaler = MediaQuery.textScalerOf($contextName);';
  return source.substring(0, insertAt) + declaration + source.substring(insertAt);
}

bool textWidgetsMissingScaler(String source) {
  for (final match in _textWidgetRe.allMatches(source)) {
    final callStart = match.end - 1;
    final callEnd = findMatchingParen(source, callStart);
    if (callEnd == null) {
      continue;
    }
    final call = source.substring(callStart, callEnd + 1);
    if (!call.contains('textScaler:')) {
      return true;
    }
  }
  return false;
}

String attachTextScalerToTextWidgets(String source) {
  final parts = <String>[];
  var index = 0;
  for (final match in _textWidgetRe.allMatches(source)) {
    final textStart = match.start;
    var prefix = source.substring(index, textStart);
    prefix = prefix.replaceAll(_constBeforeTextRe, '');
    parts.add(prefix);

    final callStart = match.end - 1;
    final callEnd = findMatchingParen(source, callStart);
    if (callEnd == null) {
      parts.add(source.substring(textStart));
      return parts.join();
    }

    if (source.substring(textStart, callEnd + 1).contains('textScaler:')) {
      parts.add(source.substring(textStart, callEnd + 1));
    } else {
      final contextName = contextNameForPosition(source, textStart);
      if (contextName == null) {
        parts.add(source.substring(textStart, callEnd + 1));
      } else {
        parts.add(patchTextCall(source, textStart, callEnd, contextName));
      }
    }
    index = callEnd + 1;
  }
  parts.add(source.substring(index));
  return parts.join();
}

String stripConstAroundRuntimeTextScaler(String source) {
  if (!source.contains(_runtimeTextScaler)) {
    return source;
  }
  var updated = source;
  while (true) {
    final stripped = stripOneConstAroundRuntimeTextScaler(updated);
    if (stripped == updated) {
      break;
    }
    updated = stripped;
  }
  return updated.replaceAllMapped(
    RegExp(r'(\breturn\s+)const\s+(?=\w+\s*\()'),
    (match) => match.group(1)!,
  );
}

String stripOneConstAroundRuntimeTextScaler(String source) {
  final matches = RegExp(r'\bconst\s+').allMatches(source).toList().reversed;
  for (final match in matches) {
    final exprStart = match.end;
    if (exprStart >= source.length) {
      continue;
    }
    final exprEnd = constExpressionEnd(source, exprStart);
    if (exprEnd == null) {
      continue;
    }
    if (source.substring(exprStart, exprEnd).contains(_runtimeTextScaler)) {
      return source.substring(0, match.start) + source.substring(match.end);
    }
  }
  return source;
}

int? constExpressionEnd(String source, int start) {
  if (start >= source.length) {
    return null;
  }
  final char = source[start];
  if (char == '[') {
    final close = findMatchingBracket(source, start, '[', ']');
    return close == null ? null : close + 1;
  }
  if (char == '{') {
    final close = findMatchingBracket(source, start, '{', '}');
    return close == null ? null : close + 1;
  }
  if (char == '(') {
    final close = findMatchingParen(source, start);
    return close == null ? null : close + 1;
  }
  final widgetMatch = RegExp(r'\w+\s*\(').matchAsPrefix(source, start);
  if (widgetMatch == null) {
    return null;
  }
  final parenStart = start + widgetMatch.end - 1;
  final close = findMatchingParen(source, parenStart);
  return close == null ? null : close + 1;
}

String? buildContextParamBeforeBrace(String source, int braceIndex) {
  final prefix = source.substring(0, braceIndex).trimRight();
  if (prefix.isEmpty || prefix[prefix.length - 1] != ')') {
    return null;
  }
  final closeParen = prefix.length - 1;
  final openParen = findMatchingParenBackwards(prefix, closeParen);
  if (openParen == null) {
    return null;
  }
  return buildContextNameFromParamList(prefix.substring(openParen + 1, closeParen));
}

String? buildContextNameFromParamList(String paramRegion) {
  final match = _buildContextParamRe.firstMatch(paramRegion);
  if (match != null) {
    return match.group(1);
  }
  final trimmed = paramRegion.trim();
  if (trimmed.isEmpty) {
    return null;
  }
  final first = trimmed.split(',').first.trim();
  final typed = RegExp(r'^BuildContext\s+(\w+)$').firstMatch(first);
  if (typed != null) {
    return typed.group(1);
  }
  if (RegExp(r'^\w+$').hasMatch(first)) {
    return first;
  }
  return null;
}

bool isClassMethodBody(String source, int bodyOpen) {
  final windowStart = bodyOpen > 320 ? bodyOpen - 320 : 0;
  final window = source.substring(windowStart, bodyOpen);
  return RegExp(
    r'(?:^|\n)[ \t]*(?:@\w+(?:\([^\)]*\))?\s*\n[ \t]*)?'
    r'(?:Widget|void|bool|int|String|double|Future|List|Map|\w+)'
    r'\s+\w+\s*\([^)]*\)\s*(?:async\s*)?\{\s*$',
    multiLine: true,
  ).hasMatch(window);
}

String? buildMethodContextName(String source) {
  final match = _buildMethodRe.firstMatch(source);
  return match?.group(1);
}

bool methodParamsIncludeBuildContext(String params) {
  return _buildContextParamRe.hasMatch(params);
}

String prefixHelperCallsWithContext(
  String source,
  String methodName,
  String contextName,
) {
  final pattern = RegExp('\\b${RegExp.escape(methodName)}\\s*\\(([^)]*)\\)');
  return source.replaceAllMapped(pattern, (match) {
    final tail = source.substring(match.end);
    if (RegExp(r'^\s*\{').hasMatch(tail)) {
      return match.group(0)!;
    }
    final args = (match.group(1) ?? '').trim();
    if (args.isEmpty) {
      return '$methodName($contextName)';
    }
    final firstArg = args.split(',').first.trim();
    if (firstArg == contextName) {
      return match.group(0)!;
    }
    return '$methodName($contextName, $args)';
  });
}

String ensureHelperMethodsHaveBuildContext(String source) {
  final buildContextName = buildMethodContextName(source);
  var updated = source;
  for (final match in _helperMethodSignatureRe.allMatches(updated).toList()) {
    final params = (match.group(3) ?? '').trim();
    if (methodParamsIncludeBuildContext(params)) {
      continue;
    }
    final bodyOpen = match.end - 1;
    final bodyClose = findMatchingBracket(updated, bodyOpen, '{', '}');
    if (bodyClose == null) {
      continue;
    }
    final body = updated.substring(bodyOpen, bodyClose + 1);
    var needsContext = _contextReferenceRe.hasMatch(body);
    if (!needsContext && _textWidgetRe.hasMatch(body)) {
      needsContext = textWidgetsMissingScaler(body);
    }
    if (!needsContext) {
      continue;
    }
    final methodName = match.group(2)!;
    final newParams = params.isEmpty ? 'BuildContext context' : 'BuildContext context, $params';
    final signature = match.group(0)!;
    final newSignature = signature.replaceFirst(
      '$methodName(${match.group(3)})',
      '$methodName($newParams)',
    );
    updated = updated.replaceFirst(signature, newSignature);
    if (buildContextName != null) {
      updated = prefixHelperCallsWithContext(updated, methodName, buildContextName);
    }
  }
  return updated;
}

String? contextNameForPosition(String source, int index) {
  var searchEnd = index;
  while (true) {
    final bodyOpen = findEnclosingBraceOpen(source, searchEnd);
    if (bodyOpen == null) {
      return null;
    }
    final contextName = buildContextParamBeforeBrace(source, bodyOpen);
    if (contextName != null) {
      return contextName;
    }
    if (isClassMethodBody(source, bodyOpen)) {
      return null;
    }
    if (bodyOpen == 0) {
      return null;
    }
    searchEnd = bodyOpen - 1;
  }
}

String patchTextCall(
  String source,
  int textStart,
  int callEnd,
  String contextName,
) {
  final openParen = source.indexOf('(', textStart);
  if (openParen < 0 || openParen > callEnd) {
    return source.substring(textStart, callEnd + 1);
  }
  final ctor = source.substring(textStart, openParen).trim();
  final scaler = 'textScaler: MediaQuery.textScalerOf($contextName)';
  final inner = source.substring(openParen + 1, callEnd).trim();
  if (inner.isEmpty) {
    return '$ctor($scaler)';
  }
  if (inner.endsWith(',')) {
    return '$ctor($inner $scaler)';
  }
  return '$ctor($inner, $scaler)';
}
