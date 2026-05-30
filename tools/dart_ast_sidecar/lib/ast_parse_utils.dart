import 'package:analyzer/dart/analysis/utilities.dart';
import 'package:analyzer/dart/ast/ast.dart';

class ParsedDartSource {
  ParsedDartSource({
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

  int? toWrappedOffset(int sourceOffset) => sourceOffset + this.sourceOffset;
}

bool looksLikeCompilationUnit(String source) {
  final trimmed = source.trimLeft();
  return trimmed.startsWith('import ') ||
      trimmed.startsWith('part ') ||
      trimmed.startsWith('class ') ||
      trimmed.startsWith('enum ') ||
      trimmed.startsWith('mixin ') ||
      trimmed.startsWith('@') ||
      trimmed.startsWith('void main');
}

String stripTrailingSemicolon(String source) {
  final trimmed = source.trimRight();
  if (trimmed.endsWith(';')) {
    return trimmed.substring(0, trimmed.length - 1).trimRight();
  }
  return trimmed;
}

CompilationUnit? parseCompilationUnit(String content) {
  final result = parseString(content: content, throwIfDiagnostics: false);
  return result.unit;
}

ParsedDartSource? parseDartSource(String source) {
  if (looksLikeCompilationUnit(source)) {
    final unit = parseCompilationUnit(source);
    if (unit != null) {
      return ParsedDartSource(unit: unit, source: source, sourceOffset: 0);
    }
    return null;
  }
  final expression = stripTrailingSemicolon(source);
  const preamble = 'void __figmaSyntaxRepair() {\n  final __figmaSyntaxExpr = ';
  const suffix = ';\n}';
  final wrapped = '$preamble$expression$suffix';
  final unit = parseCompilationUnit(wrapped);
  if (unit == null) {
    return null;
  }
  return ParsedDartSource(
    unit: unit,
    source: expression,
    sourceOffset: preamble.length,
  );
}

class SourceEdit {
  SourceEdit(this.start, this.end, this.replacement);

  final int start;
  final int end;
  final String replacement;
}

String applySourceEdits(String source, List<SourceEdit> edits) {
  if (edits.isEmpty) {
    return source;
  }
  final sorted = List<SourceEdit>.from(edits)
    ..sort((a, b) => b.start.compareTo(a.start));
  var updated = source;
  for (final edit in sorted) {
    updated = updated.replaceRange(edit.start, edit.end, edit.replacement);
  }
  return updated;
}
