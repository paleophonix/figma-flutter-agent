String unscaleDesignExpressions(String source) {
  var updated = source;
  final patterns = <RegExp>[
    RegExp(r'(\d+(?:\.\d+)?)\s*\*\s*scaleX\b'),
    RegExp(r'(\d+(?:\.\d+)?)\s*\*\s*scaleY\b'),
    RegExp(r'(\d+(?:\.\d+)?)\s*\*\s*scale\b'),
  ];
  for (final pattern in patterns) {
    updated = updated.replaceAllMapped(pattern, (m) => m.group(1)!);
  }
  updated = updated.replaceAll(
    RegExp(r'width:\s*constraints\.maxWidth\b'),
    'width: designWidth',
  );
  updated = updated.replaceAll(
    RegExp(r'height:\s*designHeight\s*\*\s*scaleY\b'),
    'height: designHeight',
  );
  return updated;
}
