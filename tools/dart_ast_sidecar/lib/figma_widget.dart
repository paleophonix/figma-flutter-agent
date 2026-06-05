import 'package:analyzer/dart/analysis/utilities.dart';
import 'package:analyzer/dart/ast/ast.dart';
import 'package:analyzer/dart/ast/visitor.dart';

String sanitizeFigmaKeyToken(String figmaId) {
  final buffer = StringBuffer();
  for (final codeUnit in figmaId.codeUnits) {
    final ch = String.fromCharCode(codeUnit);
    if (RegExp(r'[A-Za-z0-9_-]').hasMatch(ch)) {
      buffer.write(ch);
    } else {
      buffer.write('_');
    }
  }
  var safe = buffer.toString();
  if (safe.isEmpty) {
    safe = 'unknown';
  }
  if (RegExp(r'^\d').hasMatch(safe)) {
    safe = 'n_$safe';
  }
  return safe;
}

String figmaKeyToken(String figmaId) {
  return 'figma-${sanitizeFigmaKeyToken(figmaId)}';
}

String? extractWidgetByFigmaKey(String source, String figmaId) {
  final parsed = _parseSource(source);
  if (parsed == null) {
    return null;
  }
  final visitor = _FigmaWidgetExtractor(parsed, figmaKeyToken(figmaId));
  parsed.unit.accept(visitor);
  return visitor.snippet;
}

String? replaceWidgetByFigmaKey(
  String source,
  String figmaId,
  String replacement,
) {
  final outcome = replaceWidgetByFigmaKeyDetailed(source, figmaId, replacement);
  return outcome.source;
}

class ReplaceWidgetOutcome {
  const ReplaceWidgetOutcome._({this.source, this.error});

  const ReplaceWidgetOutcome.success(String updated)
      : this._(source: updated);

  const ReplaceWidgetOutcome.widgetNotFound()
      : this._(error: 'widget_not_found');

  const ReplaceWidgetOutcome.invalidReplacement()
      : this._(error: 'invalid_replacement');

  final String? source;
  final String? error;
}

ReplaceWidgetOutcome replaceWidgetByFigmaKeyDetailed(
  String source,
  String figmaId,
  String replacement,
) {
  final parsed = _parseSource(source);
  if (parsed == null) {
    return const ReplaceWidgetOutcome.widgetNotFound();
  }
  final visitor = _FigmaWidgetExtractor(parsed, figmaKeyToken(figmaId));
  parsed.unit.accept(visitor);
  if (visitor.snippet == null || visitor.start == null || visitor.end == null) {
    return const ReplaceWidgetOutcome.widgetNotFound();
  }
  final trimmed = replacement.trim();
  if (trimmed.isEmpty) {
    return const ReplaceWidgetOutcome.widgetNotFound();
  }
  final original = source;
  final snippet = visitor.snippet!;
  final index = original.indexOf(snippet);
  final updated = index >= 0
      ? original.replaceRange(index, index + snippet.length, trimmed)
      : source.replaceRange(visitor.start!, visitor.end!, trimmed);
  if (_parseSource(updated) == null) {
    return const ReplaceWidgetOutcome.invalidReplacement();
  }
  return ReplaceWidgetOutcome.success(updated);
}

class _ParsedSource {
  _ParsedSource({
    required this.unit,
    required this.source,
    required this.sourceOffset,
  });

  final CompilationUnit unit;
  final String source;
  final int sourceOffset;

  int? toSourceOffset(int wrappedOffset) {
    final relative = wrappedOffset - sourceOffset;
    if (relative < 0 || relative > source.length) {
      return null;
    }
    return relative;
  }
}

bool _looksLikeCompilationUnit(String source) {
  final trimmed = source.trimLeft();
  return trimmed.startsWith('import ') ||
      trimmed.startsWith('part ') ||
      trimmed.startsWith('class ') ||
      trimmed.startsWith('enum ') ||
      trimmed.startsWith('mixin ') ||
      trimmed.startsWith('@') ||
      trimmed.startsWith('void main');
}

_ParsedSource? _parseSource(String source) {
  if (_looksLikeCompilationUnit(source)) {
    final unit = _parseCompilationUnit(source);
    if (unit != null) {
      return _ParsedSource(unit: unit, source: source, sourceOffset: 0);
    }
  }
  final expression = _stripTrailingSemicolon(source);
  const preamble = 'void __figmaAstSidecarWrap() {\n  final __figmaAstExpr = ';
  const suffix = ';\n}';
  final wrapped = '$preamble$expression$suffix';
  final unit = _parseCompilationUnit(wrapped);
  if (unit == null) {
    return null;
  }
  return _ParsedSource(
    unit: unit,
    source: expression,
    sourceOffset: preamble.length,
  );
}

String _stripTrailingSemicolon(String source) {
  final trimmed = source.trimRight();
  if (trimmed.endsWith(';')) {
    return trimmed.substring(0, trimmed.length - 1).trimRight();
  }
  return trimmed;
}

CompilationUnit? _parseCompilationUnit(String content) {
  final result = parseString(content: content, throwIfDiagnostics: false);
  if (result.errors.isNotEmpty) {
    return null;
  }
  return result.unit;
}

class _FigmaWidgetExtractor extends RecursiveAstVisitor<void> {
  _FigmaWidgetExtractor(this.parsed, this.token);

  final _ParsedSource parsed;
  final String token;
  String? snippet;
  int? start;
  int? end;

  @override
  void visitMethodInvocation(MethodInvocation node) {
    if (snippet == null) {
      _captureIfFigmaKey(node.argumentList, node.offset, node.end);
    }
    super.visitMethodInvocation(node);
  }

  @override
  void visitInstanceCreationExpression(InstanceCreationExpression node) {
    if (snippet == null) {
      _captureIfFigmaKey(node.argumentList, node.offset, node.end);
    }
    super.visitInstanceCreationExpression(node);
  }

  void _captureIfFigmaKey(ArgumentList? argumentList, int wrappedStart, int wrappedEnd) {
    if (!_argumentListHasValueKey(argumentList, token)) {
      return;
    }
    final relStart = parsed.toSourceOffset(wrappedStart);
    final relEnd = parsed.toSourceOffset(wrappedEnd);
    if (relStart == null || relEnd == null || relStart > relEnd) {
      return;
    }
    start = relStart;
    end = relEnd;
    snippet = parsed.source.substring(relStart, relEnd);
  }

}

bool _argumentListHasValueKey(ArgumentList? argumentList, String token) {
  if (argumentList == null) {
    return false;
  }
  for (final arg in argumentList.arguments) {
    if (arg is! NamedExpression) {
      continue;
    }
    if (arg.name.label.name != 'key') {
      continue;
    }
    if (_expressionHasValueKeyToken(arg.expression, token)) {
      return true;
    }
  }
  return false;
}

bool _expressionHasValueKeyToken(Expression expression, String token) {
  ArgumentList? argumentList;
  String? typeName;
  if (expression is MethodInvocation) {
    typeName = expression.methodName.name;
    argumentList = expression.argumentList;
  } else if (expression is InstanceCreationExpression) {
    typeName = expression.constructorName.type.name2.lexeme;
    argumentList = expression.argumentList;
  }
  if (typeName != 'ValueKey' || argumentList == null) {
    return false;
  }
  final args = argumentList.arguments;
  if (args.isEmpty) {
    return false;
  }
  final first = args.first;
  if (first is StringLiteral) {
    return first.stringValue == token;
  }
  return false;
}
