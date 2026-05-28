import 'rules_delimiters.dart'
    show
        findExpressionEnd,
        findMatchingBracket,
        findMatchingParen,
        findNamedParamValueStartInRegion;
import 'rules_layout_unscale.dart';

final _layoutBuilderRe = RegExp(r'LayoutBuilder\s*\(\s*builder:\s*\(');
final _scaleFromConstraintsRe = RegExp(
  r'final\s+double\s+scaleX\s*=\s*constraints\.maxWidth\s*/\s*designWidth',
);

final _screenScaleTransformRe = RegExp(
  r'Transform\.scale\s*\(\s*scale:\s*(?:screenScale|screenWidth\s*/\s*canvasWidth)\b',
);
final _screenScaleDeclRe = RegExp(
  r'^[ \t]*final\s+double\s+screenScale\s*=.*?;\s*\n?',
  multiLine: true,
);
final _screenWidthForScaleDeclRe = RegExp(
  r'^[ \t]*final\s+double\s+screenWidth\s*=\s*MediaQuery\.of\([^)]+\)\.size\.width;\s*\n?',
  multiLine: true,
);

String stripViewportScaleHack(String source) {
  var updated = source;
  var searchFrom = 0;
  while (true) {
    final slice = updated.substring(searchFrom);
    final match = _screenScaleTransformRe.firstMatch(slice);
    if (match == null) {
      break;
    }
    final matchStart = searchFrom + match.start;
    final openParen = updated.indexOf('(', matchStart);
    if (openParen < 0) {
      break;
    }
    final closeParen = findMatchingParen(updated, openParen);
    if (closeParen == null || closeParen < openParen) {
      break;
    }
    final inner = updated.substring(openParen + 1, closeParen);
    final childValueStartInInner = findNamedParamValueStartInRegion(inner, 'child');
    if (childValueStartInInner == null) {
      searchFrom = closeParen + 1;
      continue;
    }
    final childStart = openParen + 1 + childValueStartInInner;
    final childEnd = findExpressionEnd(updated, childStart);
    if (childEnd == null || childEnd <= childStart) {
      searchFrom = closeParen + 1;
      continue;
    }
    final childExpr = updated.substring(childStart, childEnd).trim();
    updated = updated.replaceRange(matchStart, closeParen + 1, childExpr);
    searchFrom = matchStart + childExpr.length;
  }
  updated = updated.replaceAll(_screenScaleDeclRe, '');
  updated = updated.replaceAll(_screenWidthForScaleDeclRe, '');
  return updated;
}

String stripResponsiveLayoutBuilder(String source) {
  var updated = source;
  var searchFrom = 0;
  while (true) {
    final slice = updated.substring(searchFrom);
    final match = _layoutBuilderRe.firstMatch(slice);
    if (match == null) {
      break;
    }
    final matchStart = searchFrom + match.start;
    final openParen = updated.indexOf('(', matchStart);
    if (openParen < 0) {
      break;
    }
    final closeParen = findMatchingParen(updated, openParen);
    if (closeParen == null || closeParen < openParen) {
      break;
    }
    final block = updated.substring(matchStart, closeParen + 1);
    final stackWidget = _extractResponsiveLayoutBuilderStack(block);
    if (stackWidget == null) {
      searchFrom = closeParen + 1;
      continue;
    }
    updated = updated.replaceRange(matchStart, closeParen + 1, stackWidget);
    searchFrom = matchStart + stackWidget.length;
  }
  return updated;
}

String? _extractResponsiveLayoutBuilderStack(String block) {
  if (!block.contains('scaleX') && !_scaleFromConstraintsRe.hasMatch(block)) {
    return null;
  }
  final builderIdx = block.indexOf('builder:');
  if (builderIdx < 0) {
    return null;
  }
  final paramsOpen = block.indexOf('(', builderIdx);
  if (paramsOpen < 0) {
    return null;
  }
  final paramsClose = findMatchingParen(block, paramsOpen);
  if (paramsClose == null || paramsClose < paramsOpen) {
    return null;
  }
  var bodyIndex = paramsClose + 1;
  while (bodyIndex < block.length && ' \t\n\r'.contains(block[bodyIndex])) {
    bodyIndex++;
  }
  if (bodyIndex >= block.length || block[bodyIndex] != '{') {
    return null;
  }
  final bodyClose = findMatchingBracket(block, bodyIndex, '{', '}');
  if (bodyClose == null) {
    return null;
  }
  final builderBody = block.substring(bodyIndex + 1, bodyClose);
  final returnExpr = _extractBuilderReturnExpression(builderBody);
  if (returnExpr == null) {
    return null;
  }
  final stackWidget = _unwrapSingleChildWidget(returnExpr);
  if (!stackWidget.startsWith('Stack(')) {
    return null;
  }
  return unscaleDesignExpressions(stackWidget);
}

String? _extractBuilderReturnExpression(String builderBody) {
  final returns = RegExp(r'\breturn\s+').allMatches(builderBody).toList();
  if (returns.isEmpty) {
    return null;
  }
  var returnStart = returns.last.end;
  while (returnStart < builderBody.length && builderBody[returnStart].trim().isEmpty) {
    returnStart++;
  }
  final exprEnd = findExpressionEnd(builderBody, returnStart);
  if (exprEnd == null || exprEnd <= returnStart) {
    return null;
  }
  return builderBody
      .substring(returnStart, exprEnd)
      .trim()
      .replaceAll(RegExp(r'[,;]+$'), '');
}

const _unwrapPrefixes = [
  'SingleChildScrollView',
  'GestureDetector',
  'SizedBox',
  'Center',
  'FittedBox',
  'Align',
  'Padding',
];

String _unwrapSingleChildWidget(String expr) {
  var current = expr.trim().replaceAll(RegExp(r'[,;]+$'), '');
  for (var pass = 0; pass < 24; pass++) {
    if (current.startsWith('Stack(')) {
      return current;
    }
    var matched = false;
    for (final prefix in _unwrapPrefixes) {
      final token = '$prefix(';
      if (!current.startsWith(token)) {
        continue;
      }
      matched = true;
      final openParen = token.length - 1;
      final closeParen = findMatchingParen(current, openParen);
      if (closeParen == null || closeParen < openParen) {
        return current;
      }
      final inner = current.substring(openParen + 1, closeParen);
      final childValueStartInInner =
          findNamedParamValueStartInRegion(inner, 'child');
      if (childValueStartInInner == null) {
        return current;
      }
      final childStart = openParen + 1 + childValueStartInInner;
      final childEnd = findExpressionEnd(current, childStart);
      if (childEnd == null || childEnd <= childStart) {
        return current;
      }
      current = current
          .substring(childStart, childEnd)
          .trim()
          .replaceAll(RegExp(r'[,;]+$'), '');
      break;
    }
    if (!matched) {
      break;
    }
  }
  return current;
}
