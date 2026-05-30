import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

/// Axis-aligned bounds in screen-frame logical pixels (matches Figma stack placement).
class FrameBounds {
  const FrameBounds({
    required this.left,
    required this.top,
    required this.width,
    required this.height,
  });

  final double left;
  final double top;
  final double width;
  final double height;

  Map<String, double> toJson() => {
        'left': left,
        'top': top,
        'width': width,
        'height': height,
      };
}

/// Runtime geometry introspection for golden tests (four-corner AABB, scroll-aware).
class UIGeometryMapper {
  UIGeometryMapper(this.tester);

  final WidgetTester tester;

  /// Global axis-aligned bounds from all four corners of [box] (handles rotation/skew).
  Rect globalAxisAlignedBounds(RenderBox box) {
    if (!box.hasSize) {
      return Rect.zero;
    }
    final w = box.size.width;
    final h = box.size.height;
    final corners = <Offset>[
      Offset.zero,
      Offset(w, 0),
      Offset(w, h),
      Offset(0, h),
    ];
    var minX = double.infinity;
    var minY = double.infinity;
    var maxX = double.negativeInfinity;
    var maxY = double.negativeInfinity;
    for (final corner in corners) {
      final global = box.localToGlobal(corner);
      minX = global.dx < minX ? global.dx : minX;
      minY = global.dy < minY ? global.dy : minY;
      maxX = global.dx > maxX ? global.dx : maxX;
      maxY = global.dy > maxY ? global.dy : maxY;
    }
    return Rect.fromLTRB(minX, minY, maxX, maxY);
  }

  /// Scroll content offset along each axis for [element] (Figma design-space Y/X).
  Offset scrollContentBias(Element element) {
    var dx = 0.0;
    var dy = 0.0;
    element.visitAncestorElements((ancestor) {
      final widget = ancestor.widget;
      if (widget is! Scrollable) {
        return true;
      }
      final state = Scrollable.of(ancestor);
      final axis = widget.axis;
      final pixels = state.position.pixels;
      if (axis == Axis.vertical) {
        dy += pixels;
      } else {
        dx += pixels;
      }
      return true;
    });
    return Offset(dx, dy);
  }

  /// Bounds relative to [frameRoot] plus scroll content bias (Figma stack placement space).
  FrameBounds? frameBoundsForElement(
    Element element, {
    required RenderBox frameRoot,
  }) {
    final renderObject = element.findRenderObject();
    if (renderObject is! RenderBox || !renderObject.hasSize) {
      return null;
    }
    final global = globalAxisAlignedBounds(renderObject);
    final frameOrigin = frameRoot.localToGlobal(Offset.zero);
    final bias = scrollContentBias(element);
    final left = global.left - frameOrigin.dx + bias.dx;
    final top = global.top - frameOrigin.dy + bias.dy;
    return FrameBounds(
      left: left,
      top: top,
      width: global.width,
      height: global.height,
    );
  }

  RenderBox? screenFrameRoot(Type screenType) {
    final finder = find.byType(screenType);
    if (finder.evaluate().isEmpty) {
      return null;
    }
    final renderObject = tester.element(finder).findRenderObject();
    if (renderObject is! RenderBox || !renderObject.hasSize) {
      return null;
    }
    return renderObject;
  }

  /// Collect ``figma-*`` key bounds under [screenType] in design-frame coordinates.
  Map<String, FrameBounds> collectFigmaKeyBounds(Type screenType) {
    final results = <String, FrameBounds>{};
    final frameRoot = screenFrameRoot(screenType);
    if (frameRoot == null) {
      return results;
    }

    void visit(Element element) {
      final widget = element.widget;
      final key = widget.key;
      if (key is ValueKey<String>) {
        final value = key.value;
        if (value.startsWith('figma-')) {
          final token = value.substring('figma-'.length);
          final bounds = frameBoundsForElement(
            element,
            frameRoot: frameRoot,
          );
          if (bounds != null) {
            results[token] = bounds;
          }
        }
      }
      element.visitChildren(visit);
    }

    visit(tester.element(find.byType(screenType)));
    return results;
  }

  /// Legacy ``Rect`` map (frame-relative, scroll-adjusted).
  Map<String, Rect> collectFigmaKeyRects(Type screenType) {
    final bounds = collectFigmaKeyBounds(screenType);
    return {
      for (final entry in bounds.entries)
        entry.key: Rect.fromLTWH(
          entry.value.left,
          entry.value.top,
          entry.value.width,
          entry.value.height,
        ),
    };
  }

  Rect? rectForFigmaToken(String token, Type screenType) {
    return collectFigmaKeyRects(screenType)[token];
  }
}

/// Back-compat alias used by existing golden tests.
class ElementCoordinateMapper {
  ElementCoordinateMapper(this.tester) : _geometry = UIGeometryMapper(tester);

  final WidgetTester tester;
  final UIGeometryMapper _geometry;

  Rect? rectForFigmaToken(String token) {
    final finder = find.byKey(ValueKey<String>('figma-$token'));
    if (finder.evaluate().isEmpty) {
      return null;
    }
    final renderObject = tester.element(finder).findRenderObject();
    if (renderObject is! RenderBox || !renderObject.hasSize) {
      return null;
    }
    return _geometry.globalAxisAlignedBounds(renderObject);
  }

  Map<String, Rect> collectFigmaKeyRects(Type screenType) {
    return _geometry.collectFigmaKeyRects(screenType);
  }
}
