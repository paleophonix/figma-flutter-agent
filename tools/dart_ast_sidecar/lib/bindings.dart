/// One Figma binding discovered in Dart source (ValueKey or custom-code zone).
class BindingRecord {
  BindingRecord({
    required this.nodeId,
    required this.kind,
    required this.line,
    this.role,
  });

  final String nodeId;
  final String kind;
  final int line;
  final String? role;

  Map<String, Object?> toJson() => {
        'nodeId': nodeId,
        'kind': kind,
        'line': line,
        if (role != null) 'role': role,
      };
}

final _valueKeyPattern = RegExp(
  "ValueKey(?:<[^>]+>)?\\(\\s*['\"]figma-([^'\"]+)['\"]",
);
final _zonePattern = RegExp(r'custom-code:([\w.:+-]+)');

String _tokenToNodeId(String token) {
  return token.replaceAll('_', ':');
}

String _nodeIdFromZone(String zone) {
  if (!zone.startsWith('figma-')) {
    return zone;
  }
  final base = zone.contains(':') ? zone.split(':').first : zone;
  return base.replaceFirst('figma-', '').replaceAll('_', ':');
}

String? _roleFromZone(String zone) {
  if (!zone.contains(':')) {
    return null;
  }
  return zone.split(':').last;
}

/// List Figma node bindings in [source] (ValueKey + custom-code markers).
List<BindingRecord> listBindings(String source) {
  final records = <BindingRecord>[];
  final lines = source.split('\n');
  for (var index = 0; index < lines.length; index++) {
    final line = lines[index];
    final lineNo = index + 1;
    for (final match in _valueKeyPattern.allMatches(line)) {
      records.add(
        BindingRecord(
          nodeId: _tokenToNodeId(match.group(1)!),
          kind: 'valueKey',
          line: lineNo,
        ),
      );
    }
    for (final match in _zonePattern.allMatches(line)) {
      final zone = match.group(1)!;
      records.add(
        BindingRecord(
          nodeId: _nodeIdFromZone(zone),
          kind: 'comment',
          line: lineNo,
          role: _roleFromZone(zone),
        ),
      );
    }
  }
  return records;
}
