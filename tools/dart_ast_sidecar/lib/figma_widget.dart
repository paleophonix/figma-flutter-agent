import 'package:analyzer/dart/analysis/utilities.dart';
import 'package:analyzer/dart/ast/ast.dart';
import 'package:analyzer/dart/ast/visitor.dart';

String figmaKeyToken(String figmaId) {
  final safe = figmaId.replaceAll(':', '_').replaceAll("'", r"\'");
  return 'figma-$safe';
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
  final parsed = _parseSource(source);
  if (parsed == null) {
    return null;
  }
  final visitor = _FigmaWidgetExtractor(parsed, figmaKeyToken(figmaId));
  parsed.unit.accept(visitor);
  if (visitor.snippet == null || visitor.start == null || visitor.end == null) {
    return null;
  }
  final trimmed = replacement.trim();
  if (trimmed.isEmpty) {
    return null;
  }
  final original = source;
  final snippet = visitor.snippet!;
  final index = original.indexOf(snippet);
  if (index >= 0) {
    return original.replaceRange(index, index + snippet.length, trimmed);
  }
  return source.replaceRange(visitor.start!, visitor.end!, trimmed);
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
