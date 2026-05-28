class _ScanState {
  bool inString = false;
  String quote = '';
  bool escape = false;
  bool inLineComment = false;
  bool inBlockComment = false;
  int parenDepth = 0;
  int braceDepth = 0;
  int bracketDepth = 0;

  void advance(String source, int index) {
    final ch = source[index];
    if (inLineComment) {
      if (ch == '\n') {
        inLineComment = false;
      }
      return;
    }
    if (inBlockComment) {
      if (ch == '*' &&
          index + 1 < source.length &&
          source[index + 1] == '/') {
        inBlockComment = false;
      }
      return;
    }
    if (inString) {
      if (escape) {
        escape = false;
        return;
      }
      if (ch == r'\') {
        escape = true;
        return;
      }
      if (ch == quote) {
        inString = false;
      }
      return;
    }
    if (ch == '/' && index + 1 < source.length) {
      final next = source[index + 1];
      if (next == '/') {
        inLineComment = true;
        return;
      }
      if (next == '*') {
        inBlockComment = true;
        return;
      }
    }
    if (ch == "'" || ch == '"') {
      inString = true;
      quote = ch;
      return;
    }
    if (ch == '(') {
      parenDepth++;
    } else if (ch == ')') {
      if (parenDepth > 0) {
        parenDepth--;
      }
    } else if (ch == '{') {
      braceDepth++;
    } else if (ch == '}') {
      if (braceDepth > 0) {
        braceDepth--;
      }
    } else if (ch == '[') {
      bracketDepth++;
    } else if (ch == ']') {
      if (bracketDepth > 0) {
        bracketDepth--;
      }
    }
  }

  bool get inLiteral =>
      inString || inLineComment || inBlockComment;
}

bool _isIdentBoundary(String source, int index) {
  if (index <= 0) {
    return true;
  }
  final prev = source[index - 1];
  return !_isIdentChar(prev);
}

bool _isIdentChar(String ch) {
  if (ch.length != 1) {
    return false;
  }
  final code = ch.codeUnitAt(0);
  return (code >= 65 && code <= 90) ||
      (code >= 97 && code <= 122) ||
      (code >= 48 && code <= 57) ||
      ch == '_' ||
      ch == r'$';
}

int? _findNamedParamValueStart(
  String source,
  String paramName, {
  required int matchParenDepth,
}) {
  final token = '$paramName:';
  final state = _ScanState();
  for (var i = 0; i < source.length; i++) {
    if (!state.inLiteral &&
        state.parenDepth == matchParenDepth &&
        state.braceDepth == 0 &&
        state.bracketDepth == 0 &&
        _isIdentBoundary(source, i) &&
        source.startsWith(token, i)) {
      var valueStart = i + token.length;
      while (valueStart < source.length && source[valueStart].trim().isEmpty) {
        valueStart++;
      }
      return valueStart;
    }
    state.advance(source, i);
  }
  return null;
}

/// Value start offset inside a widget argument list region (no outer call parens).
int? findNamedParamValueStartInRegion(String region, String paramName) {
  return _findNamedParamValueStart(region, paramName, matchParenDepth: 0);
}

/// Value start offset inside a full ``WidgetName(...)`` call block.
int? findNamedParamValueStartInCall(String source, String paramName) {
  return _findNamedParamValueStart(source, paramName, matchParenDepth: 1);
}

_ScanState _scanStateAt(String source, int index) {
  final state = _ScanState();
  final bound = index < 0
      ? 0
      : index > source.length
          ? source.length
          : index;
  for (var i = 0; i < bound; i++) {
    state.advance(source, i);
  }
  return state;
}

int? findMatchingParen(String source, int openIndex) {
  if (openIndex < 0 || openIndex >= source.length || source[openIndex] != '(') {
    return null;
  }
  var depth = 0;
  var inString = false;
  var quote = '';
  var escape = false;
  for (var i = openIndex; i < source.length; i++) {
    final ch = source[i];
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (ch == r'\') {
        escape = true;
        continue;
      }
      if (ch == quote) {
        inString = false;
      }
      continue;
    }
    if (ch == "'" || ch == '"') {
      inString = true;
      quote = ch;
      continue;
    }
    if (ch == '(') {
      depth++;
    } else if (ch == ')') {
      depth--;
      if (depth == 0) {
        return i;
      }
    }
  }
  return null;
}

int? findExpressionEnd(String source, int start) {
  if (start < 0 || start > source.length) {
    return null;
  }
  var index = start;
  while (index < source.length && source[index].trim().isEmpty) {
    index++;
  }
  if (index >= source.length) {
    return index >= start ? index : null;
  }
  final prefixState = _scanStateAt(source, index);
  if (prefixState.inLiteral) {
    return null;
  }
  if (source.startsWith('const ', index)) {
    index += 'const '.length;
    while (index < source.length && source[index].trim().isEmpty) {
      index++;
    }
    if (index >= source.length) {
      return null;
    }
    final afterConst = _scanStateAt(source, index);
    if (afterConst.inLiteral) {
      return null;
    }
  }
  final char = source[index];
  if (char == '(') {
    final close = findMatchingParen(source, index);
    if (close == null || close < index) {
      return null;
    }
    var end = close + 1;
    while (end < source.length && source[end].trim().isEmpty) {
      end++;
    }
    if (end < source.length && source[end] == '{') {
      final bodyClose = findMatchingBracket(source, end, '{', '}');
      if (bodyClose != null && bodyClose >= end) {
        return bodyClose + 1;
      }
    }
    return end >= index ? end : null;
  }
  final state = _scanStateAt(source, index);
  for (var position = index; position < source.length; position++) {
    final charAt = source[position];
    if (state.inLiteral) {
      state.advance(source, position);
      continue;
    }
    if (charAt == '(') {
      state.parenDepth++;
    } else if (charAt == ')') {
      if (state.parenDepth == 0) {
        return position >= index ? position : null;
      }
      state.parenDepth--;
    } else if (charAt == '{') {
      state.braceDepth++;
    } else if (charAt == '}') {
      if (state.braceDepth == 0) {
        return position >= index ? position : null;
      }
      state.braceDepth--;
    } else if (charAt == '[') {
      state.bracketDepth++;
    } else if (charAt == ']') {
      if (state.bracketDepth == 0) {
        return position >= index ? position : null;
      }
      state.bracketDepth--;
    } else if (charAt == ',' &&
        state.parenDepth == 0 &&
        state.braceDepth == 0 &&
        state.bracketDepth == 0) {
      return position >= index ? position : null;
    }
    state.advance(source, position);
  }
  final end = source.length;
  return end >= index ? end : null;
}

int? findMatchingBracket(
  String source,
  int openIndex,
  String openChar,
  String closeChar,
) {
  if (openIndex < 0 || openIndex >= source.length || source[openIndex] != openChar) {
    return null;
  }
  var depth = 0;
  var inString = false;
  var quote = '';
  var escape = false;
  for (var i = openIndex; i < source.length; i++) {
    final ch = source[i];
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (ch == r'\') {
        escape = true;
        continue;
      }
      if (ch == quote) {
        inString = false;
      }
      continue;
    }
    if (ch == "'" || ch == '"') {
      inString = true;
      quote = ch;
      continue;
    }
    if (ch == openChar) {
      depth++;
    } else if (ch == closeChar) {
      depth--;
      if (depth == 0) {
        return i;
      }
    }
  }
  return null;
}

int? findMatchingParenBackwards(String source, int closeIndex) {
  if (closeIndex < 0 || closeIndex >= source.length || source[closeIndex] != ')') {
    return null;
  }
  var depth = 0;
  var inString = false;
  var quote = '';
  var escape = false;
  for (var i = closeIndex; i >= 0; i--) {
    final ch = source[i];
    if (inString) {
      if (escape) {
        escape = false;
        continue;
      }
      if (ch == r'\') {
        escape = true;
        continue;
      }
      if (ch == quote) {
        inString = false;
      }
      continue;
    }
    if (ch == "'" || ch == '"') {
      inString = true;
      quote = ch;
      continue;
    }
    if (ch == ')') {
      depth++;
    } else if (ch == '(') {
      depth--;
      if (depth == 0) {
        return i;
      }
    }
  }
  return null;
}

int? findEnclosingBraceOpen(String source, int index) {
  var depth = 0;
  for (var position = index - 1; position >= 0; position--) {
    final char = source[position];
    if (char == '}') {
      depth++;
      continue;
    }
    if (char != '{') {
      continue;
    }
    if (depth == 0) {
      return position;
    }
    depth--;
  }
  return null;
}
