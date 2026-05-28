import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Test-harness helper: map Figma anchor keys to pixel rects after layout.
class ElementCoordinateMapper {
  ElementCoordinateMapper(this.tester);

  final WidgetTester tester;

  /// Return the global rect for ``ValueKey('figma-$token')``.
  Rect? rectForFigmaToken(String token) {
    final finder = find.byKey(ValueKey('figma-$token'));
    if (finder.evaluate().isEmpty) {
      return null;
    }
    return tester.getRect(finder);
  }

  /// Return rects for all ``figma-*`` keys found under [screenType].
  Map<String, Rect> collectFigmaKeyRects(Type screenType) {
    final results = <String, Rect>{};
    void visit(Element element) {
      final widget = element.widget;
      final key = widget.key;
      if (key is ValueKey<String>) {
        final value = key.value;
        if (value.startsWith('figma-')) {
          final token = value.substring('figma-'.length);
          final renderObject = element.findRenderObject();
          if (renderObject is RenderBox && renderObject.hasSize) {
            final offset = renderObject.localToGlobal(Offset.zero);
            results[token] = offset & renderObject.size;
          }
        }
      }
      element.visitChildren(visit);
    }

    final finder = find.byType(screenType);
    if (finder.evaluate().isEmpty) {
      return results;
    }
    visit(tester.element(finder));
    return results;
  }
}
