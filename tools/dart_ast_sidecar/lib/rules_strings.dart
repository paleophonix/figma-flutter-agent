/// String-literal normalization for LLM-generated Dart.
String normalizeLlmDartStringEscapes(String source) {
  final lines = source.split(RegExp(r'\r?\n'));
  if (lines.isEmpty) {
    return source;
  }
  final buffer = StringBuffer();
  for (final line in lines) {
    final stripped = line.trimLeft();
    if (stripped.startsWith('import ') || stripped.startsWith('export ')) {
      buffer.writeln(line);
      continue;
    }
    if (stripped.isEmpty) {
      buffer.writeln(line);
      continue;
    }
    buffer.writeln(_transformDartStringLiterals(line, _normalizeStringLiteralEscapes));
  }
  return buffer.toString().replaceAll(RegExp(r'\n$'), '');
}

String stripBareUnicodeEscapesOutsideLiterals(String source) {
  if (!source.contains(r'\u')) {
    return source;
  }
  final spans = _outsideStringLiteralSpans(source);
  if (spans.isEmpty) {
    return source;
  }
  final chars = source.split('');
  for (final span in spans.reversed) {
    final segment = source.substring(span.$1, span.$2);
    final cleaned = segment.replaceAll(RegExp(r'\\u[0-9a-fA-F]{4}'), '');
    if (cleaned != segment) {
      chars.replaceRange(span.$1, span.$2, cleaned.split(''));
    }
  }
  return chars.join();
}

String _normalizeStringLiteralEscapes(String inner) {
  var updated = inner
      .replaceAll(r'\\n', r'\n')
      .replaceAll(r'\\t', r'\t')
      .replaceAll(r'\\"', r'"')
      .replaceAll(r"\\'", r"'");
  if (!updated.contains(r'\u')) {
    return updated;
  }
  return updated.replaceAllMapped(RegExp(r'\\u[0-9a-fA-F]{4}'), (match) {
    try {
      return String.fromCharCode(int.parse(match.group(0)!.substring(2), radix: 16));
    } catch (_) {
      return match.group(0)!;
    }
  });
}

String _transformDartStringLiterals(String source, String Function(String) transform) {
  final parts = <String>[];
  var index = 0;
  while (index < source.length) {
    final char = source[index];
    if (char != "'" && char != '"') {
      parts.add(char);
      index++;
      continue;
    }
    final quote = char;
    final literalStart = index;
    index++;
    final innerChars = <String>[];
    var escape = false;
    while (index < source.length) {
      final current = source[index];
      if (escape) {
        innerChars.add(current);
        escape = false;
        index++;
        continue;
      }
      if (current == r'\') {
        innerChars.add(current);
        escape = true;
        index++;
        continue;
      }
      if (current == quote) {
        final inner = innerChars.join();
        parts.add('$quote${transform(inner)}$quote');
        index++;
        break;
      }
      innerChars.add(current);
      index++;
    }
    if (index >= source.length) {
      parts.add(source.substring(literalStart));
      break;
    }
  }
  return parts.join();
}

List<(int, int)> _outsideStringLiteralSpans(String source) {
  final spans = <(int, int)>[];
  var index = 0;
  var outsideStart = 0;
  while (index < source.length) {
    final char = source[index];
    if (char != "'" && char != '"') {
      index++;
      continue;
    }
    if (index > outsideStart) {
      spans.add((outsideStart, index));
    }
    final quote = char;
    index++;
    var escape = false;
    while (index < source.length) {
      final current = source[index];
      if (escape) {
        escape = false;
        index++;
        continue;
      }
      if (current == r'\') {
        escape = true;
        index++;
        continue;
      }
      if (current == quote) {
        index++;
        break;
      }
      index++;
    }
    outsideStart = index;
  }
  if (outsideStart < source.length) {
    spans.add((outsideStart, source.length));
  }
  return spans;
}
