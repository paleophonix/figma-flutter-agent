import 'package:flutter/material.dart';

/// Regression: surplus closers after LOG IN ``Text.rich`` (emit parse-gate failure).
void main() {
  final textScaler = TextScaler.noScaling;
  return Stack(
    children: [
      Positioned(
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            child: Stack(
              children: [
                Positioned(
                  child: Material(
                    type: MaterialType.transparency,
                    child: MouseRegion(
                      child: GestureDetector(
                        child: Text(
                          'SIGN UP',
                          textScaler: textScaler,
                          textAlign: TextAlign.left,
                        ),
                      ),
                    ),
                  ),
                ),
                Positioned(
                  child: Semantics(
                    child: Material(
                      type: MaterialType.transparency,
                      child: MouseRegion(
                        child: GestureDetector(
                          child: Text.rich(
                            TextSpan(
                              children: [
                                TextSpan(text: 'LOG IN'),
                              ],
                            ),
                            textScaler: textScaler,
                            textAlign: TextAlign.left)),
                  )))])))), Positioned(left: 58.0, child: Text('next')),
    ],
  );
}
