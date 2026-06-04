import 'package:analyzer/dart/ast/ast.dart';
import 'package:analyzer/dart/ast/visitor.dart';

import 'ast_parse_utils.dart';
import 'rules_delimiters.dart' show findExpressionEnd, findMatchingParen;
import 'rules_link_rich.dart';

const _textStyleOnlyParams = <String>{
  'fontSize',
  'fontWeight',
  'letterSpacing',
  'fontFamily',
  'fontFamilyFallback',
  'color',
  'height',
  'decoration',
  'decorationColor',
  'decorationStyle',
  'fontStyle',
  'leadingDistribution',
  'wordSpacing',
  'backgroundColor',
  'foreground',
  'background',
  'shadows',
};

const _misplacedChildParamNames = <String>{
  'key',
  'onPressed',
  'backgroundColor',
  'textColor',
  'text',
  'icon',
  'border',
  'required',
  'super',
};

final _lightElevatedButtonBg = RegExp(
  r'backgroundColor:\s*(?:const\s+)?Color\(0x(?:FF)?(?:FFFFFF|F2F3F7|EBEAEC|E6E6E6|FAF8F5)\)',
  caseSensitive: false,
);

bool isOrphanCommaLine(String line) {
  return line.trim() == ',';
}

String stripOrphanCommaOnlyLines(String source) {
  final lines = source.split('\n');
  if (!lines.any(isOrphanCommaLine)) {
    return source;
  }
  return lines.where((line) => !isOrphanCommaLine(line)).join('\n');
}

String stripSemicolonBeforeCloserLines(String source) {
  return source.replaceAllMapped(
    RegExp(r'\n(\s*);\s*\n(\s*[\]\)])'),
    (match) => '\n${match.group(2)}',
  );
}

String collapseDuplicateStatementSemicolons(String source) {
  return source.replaceAllMapped(RegExp(r';(\s*);'), (match) => ';');
}

/// Planned/emit delimiter balance (replaces Python ``balance_delimiters`` regex pass).
String applyPlannedDelimiterBalance(String source) {
  var updated = fixGarbageClosersAfterLinkRich(source);
  updated = collapseDuplicateStatementSemicolons(updated);
  updated = applyLlmSyntaxRepairs(updated);
  updated = stripOrphanCommaOnlyLines(updated);
  updated = stripSemicolonBeforeCloserLines(updated);
  return updated;
}

/// Full deterministic LLM syntax repair pass (replaces Python regex repairs).
String applyLlmSyntaxRepairs(String source) {
  var updated = source;
  updated = fixMisusedFlexWidgetName(updated);
  for (var pass = 0; pass < 6; pass++) {
    final before = updated;
    updated = fixMisplacedChildBeforeNamedParams(updated);
    updated = collapseDuplicateChildNamedParams(updated);
    if (updated == before) {
      break;
    }
  }
  updated = stripOrphanSemicolonOnlyLines(updated);
  updated = stripGarbageCloserOnlyLines(updated);
  updated = normalizeAppTypographyStyleReferences(updated);
  updated = stripDuplicateKeyAfterSuperSource(updated);
  updated = ensureThemeColorSchemeInScope(updated);
  updated = wrapMisplacedTextStyleParamsSource(updated);
  final parsed = parseDartSource(updated);
  if (parsed != null) {
    updated = _applyAstSyntaxRepairs(parsed);
  }
  updated = replaceImageNetworkCalls(updated);
  return updated;
}

bool isGarbageCloserOnlyLine(String line) {
  final stripped = line.trim();
  if (stripped.isEmpty) {
    return false;
  }
  for (final ch in stripped.runes) {
    final char = String.fromCharCode(ch);
    if (!'])}'.contains(char)) {
      return false;
    }
  }
  return stripped.length >= 2;
}

bool isOrphanSemicolonLine(String line) {
  final stripped = line.trim();
  if (stripped.isEmpty) {
    return false;
  }
  for (final ch in stripped.runes) {
    if (ch != 0x3B) {
      return false;
    }
  }
  return true;
}

String stripOrphanSemicolonOnlyLines(String source) {
  final lines = source.split('\n');
  if (!lines.any(isOrphanSemicolonLine)) {
    return source;
  }
  return lines.where((line) => !isOrphanSemicolonLine(line)).join('\n');
}

String stripGarbageCloserOnlyLines(String source) {
  final lines = source.split('\n');
  if (!lines.any(isGarbageCloserOnlyLine)) {
    return source;
  }
  return lines.where((line) => !isGarbageCloserOnlyLine(line)).join('\n');
}

String fixMisusedFlexWidgetName(String source) {
  return source.replaceAll('Flex(fit:', 'Flexible(fit:');
}

String collapseDuplicateChildNamedParams(String source) {
  final buffer = StringBuffer();
  var index = 0;
  while (index < source.length) {
    final state = _scanStateAt(source, index);
    if (!_tryMatchChildToken(source, index, state)) {
      buffer.write(source[index]);
      index++;
      continue;
    }
    buffer.write('child:');
    index += 'child:'.length;
    while (index < source.length && source[index].trim().isEmpty) {
      buffer.write(source[index]);
      index++;
    }
    while (true) {
      final nextState = _scanStateAt(source, index);
      if (!_tryMatchChildToken(source, index, nextState)) {
        break;
      }
      index += 'child:'.length;
      while (index < source.length && source[index].trim().isEmpty) {
        index++;
      }
    }
  }
  return buffer.toString();
}

String fixMisplacedChildBeforeNamedParams(String source) {
  final edits = <SourceEdit>[];
  var index = 0;
  while (index < source.length) {
    final state = _scanStateAt(source, index);
    if (_tryMatchChildToken(source, index, state)) {
      var cursor = index + 'child:'.length;
      while (cursor < source.length && source[cursor].trim().isEmpty) {
        cursor++;
      }
      final paramState = _scanStateAt(source, cursor);
      final param = _readNamedParamLabel(source, cursor, paramState);
      if (param != null && _misplacedChildParamNames.contains(param)) {
        edits.add(SourceEdit(index, cursor, ''));
        index = cursor;
        continue;
      }
    }
    index++;
  }
  return applySourceEdits(source, edits);
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

String ensureThemeColorSchemeInScope(String source) {
  if (!source.contains('theme.colorScheme')) {
    return source;
  }
  final hasLocalTheme = source.contains('final ThemeData theme =') ||
      (source.contains('ThemeData theme =') && source.contains('return Theme('));
  if (hasLocalTheme) {
    return source;
  }
  return source.replaceAll(
    'theme.colorScheme',
    'Theme.of(context).colorScheme',
  );
}

String stripDuplicateKeyAfterSuperSource(String source) {
  const markers = <String>[
    ', Key? key = null',
    ', Key? key',
    ', Key key = null',
    ', Key key',
  ];
  var updated = source;
  var searchFrom = 0;
  while (true) {
    final superPos = updated.indexOf('super.key', searchFrom);
    if (superPos < 0) {
      return updated;
    }
    var removed = false;
    for (final marker in markers) {
      final at = updated.indexOf(marker, superPos);
      if (at < 0 || at > superPos + 160) {
        continue;
      }
      updated = updated.replaceRange(at, at + marker.length, '');
      removed = true;
      break;
    }
    searchFrom = superPos + 'super.key'.length;
    if (!removed) {
      searchFrom++;
    }
  }
}

String wrapMisplacedTextStyleParamsSource(String source) {
  const token = 'Text(';
  final parts = <String>[];
  var index = 0;
  while (true) {
    final start = source.indexOf(token, index);
    if (start < 0) {
      parts.add(source.substring(index));
      break;
    }
    if (start > 0 && _isIdentChar(source[start - 1])) {
      parts.add(source.substring(index, start + token.length));
      index = start + token.length;
      continue;
    }
    parts.add(source.substring(index, start));
    final parenOpen = start + token.length - 1;
    final parenClose = findMatchingParen(source, parenOpen);
    if (parenClose == null) {
      parts.add(source.substring(start));
      break;
    }
    final inner = source.substring(parenOpen + 1, parenClose);
    final rebuilt = _rebuildTextCallInner(inner);
    if (rebuilt == null) {
      parts.add(source.substring(start, parenClose + 1));
    } else {
      parts.add('Text($rebuilt)');
    }
    index = parenClose + 1;
  }
  return parts.join();
}

String? _rebuildTextCallInner(String inner) {
  final args = _iterTopLevelCallArgs(inner);
  final misplaced = <_CallArg>[];
  _CallArg? styleArg;
  for (final arg in args) {
    if (arg.name != null && _textStyleOnlyParams.contains(arg.name)) {
      misplaced.add(arg);
    } else if (arg.name == 'style') {
      styleArg = arg;
    }
  }
  if (misplaced.isEmpty) {
    return null;
  }
  final styleParts = misplaced.map((a) => inner.substring(a.start, a.end).trim()).join(', ');
  final kept = <String>[];
  for (final arg in args) {
    if (arg.name != null && _textStyleOnlyParams.contains(arg.name)) {
      continue;
    }
    if (arg.name == 'style') {
      continue;
    }
    kept.add(inner.substring(arg.start, arg.end).trim());
  }
  if (styleArg != null) {
    final styleValue = inner.substring(styleArg.start, styleArg.end).trim();
    final colon = styleValue.indexOf(':');
    if (colon < 0) {
      return null;
    }
    final styleExpr = styleValue.substring(colon + 1).trim();
    if (!styleExpr.startsWith('TextStyle(')) {
      return null;
    }
    final open = styleExpr.indexOf('(');
    final close = findMatchingParen(styleExpr, open);
    if (close == null) {
      return null;
    }
    final styleInner = styleExpr.substring(open + 1, close).trim();
    final merged = styleInner.isEmpty
        ? 'style: TextStyle($styleParts)'
        : 'style: TextStyle($styleInner, $styleParts)';
    kept.add(merged);
  } else {
    kept.add('style: TextStyle($styleParts)');
  }
  return kept.join(', ');
}

class _CallArg {
  _CallArg(this.name, this.start, this.end);

  final String? name;
  final int start;
  final int end;
}

List<_CallArg> _iterTopLevelCallArgs(String inner) {
  final args = <_CallArg>[];
  var index = 0;
  while (index < inner.length) {
    while (index < inner.length && ', \t\n\r'.contains(inner[index])) {
      index++;
    }
    if (index >= inner.length) {
      break;
    }
    final argStart = index;
    String? name;
    final named = RegExp(r'^([A-Za-z_]\w*)\s*:').firstMatch(inner.substring(index));
    if (named != null && inner[index] != "'" && inner[index] != '"') {
      name = named.group(1);
      index += named.end;
    }
    while (index < inner.length && inner[index].trim().isEmpty) {
      index++;
    }
    final valueEnd = findExpressionEnd(inner, index);
    if (valueEnd == null) {
      break;
    }
    args.add(_CallArg(name, argStart, valueEnd));
    index = valueEnd;
  }
  return args;
}

String normalizeAppTypographyStyleReferences(String source) {
  var updated = source;
  updated = updated.replaceAll('const AppTypography.', 'AppTypography.');
  updated = updated.replaceAllMapped(
    RegExp(r"^[ \t]*'[^']+',[ \t]*'[^']+'\],[ \t]*\r?\n", multiLine: true),
    (_) => '',
  );
  return updated;
}

String replaceImageNetworkCalls(String source) {
  const token = 'Image.network(';
  const replacement = 'const Icon(Icons.g_mobiledata, size: 24)';
  var updated = source;
  var index = 0;
  while (true) {
    final start = updated.indexOf(token, index);
    if (start < 0) {
      return updated;
    }
    final parenOpen = start + 'Image.network'.length;
    final parenClose = findMatchingParen(updated, parenOpen);
    if (parenClose == null) {
      return updated;
    }
    updated = updated.replaceRange(start, parenClose + 1, replacement);
    index = start + replacement.length;
  }
}

String _applyAstSyntaxRepairs(ParsedDartSource parsed) {
  final rewriter = _AstSyntaxRepairVisitor(parsed);
  parsed.unit.accept(rewriter);
  return rewriter.apply();
}

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

  bool get inLiteral => inString || inLineComment || inBlockComment;
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

bool _tryMatchChildToken(String source, int index, _ScanState state) {
  if (state.inLiteral || state.parenDepth == 0) {
    return false;
  }
  if (index > 0 && _isIdentChar(source[index - 1])) {
    return false;
  }
  return source.startsWith('child:', index);
}

String? _readNamedParamLabel(String source, int index, _ScanState state) {
  if (state.inLiteral) {
    return null;
  }
  final match = RegExp(r'^([A-Za-z_]\w*)\s*:').firstMatch(source.substring(index));
  return match?.group(1);
}

class _AstSyntaxRepairVisitor extends RecursiveAstVisitor<void> {
  _AstSyntaxRepairVisitor(this.parsed);

  final ParsedDartSource parsed;
  final List<SourceEdit> _edits = [];

  String apply() => applySourceEdits(parsed.source, _edits);

  void _addEdit(int? start, int? end, String replacement) {
    if (start == null || end == null || end <= start) {
      return;
    }
    _edits.add(SourceEdit(start, end, replacement));
  }

  @override
  void visitConstructorDeclaration(ConstructorDeclaration node) {
    _stripDuplicateKeyInFormalParameters(node.parameters);
    super.visitConstructorDeclaration(node);
  }

  @override
  void visitInstanceCreationExpression(InstanceCreationExpression node) {
    final typeName = node.constructorName.type.name2.lexeme;
    if (typeName == 'ElevatedButton') {
      _repairElevatedButtonBlock(node.argumentList, node.offset, node.end);
    }
    if (typeName == 'FittedBox') {
      _repairFittedBoxInvocation(node.argumentList, node.offset, node.end);
    }
    _stripDuplicateKeyInArgumentList(node.argumentList);
    super.visitInstanceCreationExpression(node);
  }

  void _stripDuplicateKeyInFormalParameters(FormalParameterList params) {
    var sawSuperKey = false;
    final removals = <FormalParameter>[];
    for (final param in params.parameters) {
      if (param is SuperFormalParameter && param.name.lexeme == 'key') {
        sawSuperKey = true;
        continue;
      }
      if (!sawSuperKey) {
        continue;
      }
      final inner = param is DefaultFormalParameter ? param.parameter : param;
      if (inner is SimpleFormalParameter && inner.name?.lexeme == 'key') {
        final typeName = inner.type?.toSource() ?? '';
        if (typeName.contains('Key')) {
          removals.add(param);
        }
      }
    }
    for (final param in removals.reversed) {
      var start = parsed.toSourceOffset(param.offset);
      var end = parsed.toSourceOffset(param.end);
      if (start == null || end == null) {
        continue;
      }
      if (end < parsed.source.length && parsed.source[end] == ',') {
        end++;
      } else if (start > 0 && parsed.source[start - 1] == ',') {
        start--;
      }
      _addEdit(start, end, '');
    }
  }

  @override
  void visitMethodInvocation(MethodInvocation node) {
    final name = node.methodName.name;
    if (name == 'ElevatedButton') {
      _repairElevatedButtonBlock(node.argumentList, node.offset, node.end);
    }
    if (name == 'FittedBox') {
      _repairFittedBoxInvocation(node.argumentList, node.offset, node.end);
    }
    super.visitMethodInvocation(node);
  }

  void _stripDuplicateKeyInArgumentList(ArgumentList? args) {
    if (args == null) {
      return;
    }
    var sawSuperKey = args.arguments.any((arg) {
      if (arg is! NamedExpression) {
        return false;
      }
      final source = arg.toSource();
      return source.contains('super.key') ||
          (arg.name.label.name == 'key' && arg.expression is SuperExpression);
    });
    if (!sawSuperKey) {
      return;
    }
    final removals = <NamedExpression>[];
    for (final arg in args.arguments) {
      if (arg is! NamedExpression) {
        continue;
      }
      if (arg.name.label.name != 'key') {
        continue;
      }
      if (arg.expression is SuperExpression) {
        continue;
      }
      removals.add(arg);
    }
    for (final arg in removals.reversed) {
      _removeArgumentExpression(arg);
    }
  }

  void _removeArgumentExpression(Expression arg) {
    var start = parsed.toSourceOffset(arg.offset);
    var end = parsed.toSourceOffset(arg.end);
    if (start == null || end == null) {
      return;
    }
    if (end < parsed.source.length && parsed.source[end] == ',') {
      end++;
    } else if (start > 0 && parsed.source[start - 1] == ',') {
      start--;
    }
    while (start != null && start > 0 && parsed.source[start - 1].trim().isEmpty) {
      start = start - 1;
    }
    _addEdit(start, end, '');
  }

  void _repairElevatedButtonBlock(ArgumentList? args, int offset, int end) {
    final start = parsed.toSourceOffset(offset);
    final stop = parsed.toSourceOffset(end);
    if (start == null || stop == null) {
      return;
    }
    final block = parsed.source.substring(start, stop);
    if (!block.contains('backgroundColor:')) {
      return;
    }
    if (_lightElevatedButtonBg.hasMatch(block)) {
      return;
    }
    if (!block.contains('color: Color(0xFF000000)')) {
      return;
    }
    final updated = block.replaceAll(
      'color: Color(0xFF000000)',
      'color: Color(0xFFFFFFFF)',
    );
    _addEdit(start, stop, updated);
  }

  void _repairFittedBoxInvocation(ArgumentList? args, int offset, int end) {
    if (args == null) {
      return;
    }
    final start = parsed.toSourceOffset(offset);
    final stop = parsed.toSourceOffset(end);
    if (start == null || stop == null) {
      return;
    }
    final block = parsed.source.substring(start, stop);
    if (!block.contains('BoxFit.contain') || !block.contains('SizedBox(')) {
      return;
    }
    final updated = block.replaceFirst(
      'fit: BoxFit.contain',
      'fit: BoxFit.scaleDown',
    );
    if (updated != block) {
      _addEdit(start, stop, updated);
    }
  }
}
