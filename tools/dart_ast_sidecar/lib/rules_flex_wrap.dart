import 'package:analyzer/dart/analysis/utilities.dart';
import 'package:analyzer/dart/ast/ast.dart';
import 'package:analyzer/dart/ast/visitor.dart';

/// Wrap rigid [Row] / [Column] children that lack flex parent data.
String wrapFlexRowColumnChildren(String source) {
  final parsed = _parseFlexWrapSource(source);
  if (parsed == null) {
    return source;
  }
  final rewriter = _FlexWrapRewriter(parsed.source, parsed.sourceOffset);
  parsed.unit.accept(rewriter);
  return rewriter.apply();
}

class _ParsedFlexSource {
  _ParsedFlexSource({
    required this.unit,
    required this.source,
    required this.sourceOffset,
  });

  final CompilationUnit unit;
  final String source;
  final int sourceOffset;
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

_ParsedFlexSource? _parseFlexWrapSource(String source) {
  if (_looksLikeCompilationUnit(source)) {
    final result = parseString(content: source, throwIfDiagnostics: false);
    return _ParsedFlexSource(unit: result.unit, source: source, sourceOffset: 0);
  }
  final expression = _stripTrailingSemicolon(source);
  const preamble = 'void __figmaFlexWrap() {\n  final __figmaFlexExpr = ';
  const suffix = ';\n}';
  final wrapped = '$preamble$expression$suffix';
  final result = parseString(content: wrapped, throwIfDiagnostics: false);
  return _ParsedFlexSource(
    unit: result.unit,
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

class _Edit {
  _Edit(this.start, this.end, this.replacement);

  final int start;
  final int end;
  final String replacement;
}

class _FlexWrapRewriter extends RecursiveAstVisitor<void> {
  _FlexWrapRewriter(this.source, this.sourceOffset);

  final String source;
  final int sourceOffset;
  final List<_Edit> _edits = [];

  @override
  void visitMethodInvocation(MethodInvocation node) {
    final name = node.methodName.name;
    if (name == 'Row') {
      _wrapFlexChildren(node.argumentList, horizontalMainAxis: true);
    } else if (name == 'Column') {
      _wrapFlexChildren(node.argumentList, horizontalMainAxis: false);
    }
    super.visitMethodInvocation(node);
  }

  @override
  void visitInstanceCreationExpression(InstanceCreationExpression node) {
    final name = node.constructorName.type.name2.lexeme;
    if (name == 'Row') {
      _wrapFlexChildren(node.argumentList, horizontalMainAxis: true);
    } else if (name == 'Column') {
      _wrapFlexChildren(node.argumentList, horizontalMainAxis: false);
    }
    super.visitInstanceCreationExpression(node);
  }

  void _wrapFlexChildren(
    ArgumentList? argumentList, {
    required bool horizontalMainAxis,
  }) {
    final childrenArg = _namedExpression(argumentList, 'children');
    if (childrenArg == null) {
      return;
    }
    final listLiteral = childrenArg.expression;
    if (listLiteral is! ListLiteral) {
      return;
    }
    final childSnippets = <String>[];
    for (final element in listLiteral.elements) {
      if (element is! Expression) {
        continue;
      }
      final relStart = _toSourceOffset(element.offset);
      final relEnd = _toSourceOffset(element.end);
      if (relStart == null || relEnd == null || relEnd <= relStart) {
        continue;
      }
      childSnippets.add(source.substring(relStart, relEnd));
    }
    final hasCheckbox = childSnippets.any(
      (snippet) =>
          snippet.contains('Checkbox(') || snippet.contains('CupertinoCheckbox('),
    );
    for (final element in listLiteral.elements) {
      if (element is! Expression) {
        continue;
      }
      final relStart = _toSourceOffset(element.offset);
      final relEnd = _toSourceOffset(element.end);
      if (relStart == null || relEnd == null || relEnd <= relStart) {
        continue;
      }
      final snippet = source.substring(relStart, relEnd);
      if (hasCheckbox && horizontalMainAxis) {
        continue;
      }
      final wrapped = _wrapSnippetIfNeeded(snippet, horizontalMainAxis: horizontalMainAxis);
      if (wrapped == null) {
        continue;
      }
      _edits.add(_Edit(relStart, relEnd, wrapped));
    }
  }

  int? _toSourceOffset(int wrappedOffset) {
    final relative = wrappedOffset - sourceOffset;
    if (relative < 0 || relative > source.length) {
      return null;
    }
    return relative;
  }

  String apply() {
    if (_edits.isEmpty) {
      return source;
    }
    final sorted = List<_Edit>.from(_edits)
      ..sort((a, b) => b.start.compareTo(a.start));
    var updated = source;
    for (final edit in sorted) {
      updated = updated.replaceRange(edit.start, edit.end, edit.replacement);
    }
    return updated;
  }
}

NamedExpression? _namedExpression(ArgumentList? argumentList, String name) {
  if (argumentList == null) {
    return null;
  }
  for (final arg in argumentList.arguments) {
    if (arg is! NamedExpression) {
      continue;
    }
    if (arg.name.label.name == name) {
      return arg;
    }
  }
  return null;
}

String? _wrapSnippetIfNeeded(
  String snippet, {
  required bool horizontalMainAxis,
}) {
  final trimmed = snippet.trim();
  if (trimmed.isEmpty) {
    return null;
  }
  if (_alreadyFlexManaged(trimmed)) {
    return null;
  }
  if (horizontalMainAxis) {
    if (!_isRigidRowChild(trimmed)) {
      return null;
    }
    return 'Flexible(fit: FlexFit.loose, child: $trimmed)';
  }
  if (!_needsColumnCrossAxisWidth(trimmed)) {
    return null;
  }
  return 'SizedBox(width: double.infinity, child: $trimmed)';
}

bool _alreadyFlexManaged(String snippet) {
  const prefixes = [
    'Expanded(',
    'const Expanded(',
    'Flexible(',
    'const Flexible(',
    'Spacer(',
    'const Spacer(',
  ];
  for (final prefix in prefixes) {
    if (snippet.startsWith(prefix)) {
      return true;
    }
  }
  if (RegExp(r'SizedBox\s*\(\s*width:\s*double\.infinity').hasMatch(snippet)) {
    return true;
  }
  return false;
}

bool _isRigidRowChild(String snippet) {
  const roots = [
    'Text(',
    'Text.rich(',
    'Container(',
    'Image(',
    'SizedBox(',
    'ElevatedButton(',
    'OutlinedButton(',
    'TextButton(',
    'FilledButton(',
    'Icon(',
    'Padding(',
    'Align(',
    'DecoratedBox(',
    'Material(',
    'InkWell(',
    'SvgPicture',
    'ClipRRect(',
    'Opacity(',
  ];
  for (final root in roots) {
    if (snippet.startsWith(root) || snippet.startsWith('const $root')) {
      return true;
    }
  }
  return false;
}

bool _needsColumnCrossAxisWidth(String snippet) {
  if (_alreadyFlexManaged(snippet)) {
    return false;
  }
  if (RegExp(r'width:\s*double\.infinity').hasMatch(snippet)) {
    return false;
  }
  return _isRigidRowChild(snippet);
}
