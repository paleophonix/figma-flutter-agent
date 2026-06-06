final _designWidthDeclRe = RegExp(
  r'\b(?:const|final|static)\s+double\s+designWidth\b',
);
final _designHeightDeclRe = RegExp(
  r'\b(?:const|final|static)\s+double\s+designHeight\b',
);

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
  if (_designWidthDeclRe.hasMatch(updated)) {
    updated = updated.replaceAll(
      RegExp(r'width:\s*constraints\.maxWidth\b'),
      'width: designWidth',
    );
  }
  if (_designHeightDeclRe.hasMatch(updated)) {
    updated = updated.replaceAll(
      RegExp(r'height:\s*designHeight\s*\*\s*scaleY\b'),
      'height: designHeight',
    );
  }
  return updated;
}

String repairOrphanDesignCanvasIdentifiers(String source) {
  var updated = source;
  if (!_designWidthDeclRe.hasMatch(updated)) {
    updated = updated.replaceAll(RegExp(r'\bdesignWidth\b'), 'constraints.maxWidth');
  }
  if (!_designHeightDeclRe.hasMatch(updated)) {
    updated = updated.replaceAll(RegExp(r'\bdesignHeight\b'), 'constraints.maxHeight');
  }
  return updated;
}
