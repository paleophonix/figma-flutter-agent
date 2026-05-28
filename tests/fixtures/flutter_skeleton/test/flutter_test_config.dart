import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> testExecutable(FutureOr<void> Function() testMain) async {
  TestWidgetsFlutterBinding.ensureInitialized();
  await _loadPubspecFonts();
  await testMain();
}

Future<void> _loadPubspecFonts() async {
  try {
    final raw = await rootBundle.loadString('FontManifest.json');
    final manifest = json.decode(raw) as List<dynamic>;
    for (final entry in manifest) {
      if (entry is! Map<String, dynamic>) {
        continue;
      }
      final family = entry['family'] as String?;
      final faces = entry['fonts'];
      if (family == null || faces is! List<dynamic>) {
        continue;
      }
      final loader = FontLoader(family);
      for (final face in faces) {
        if (face is! Map<String, dynamic>) {
          continue;
        }
        final asset = face['asset'] as String?;
        if (asset == null) {
          continue;
        }
        loader.addFont(rootBundle.load(asset));
      }
      await loader.load();
    }
  } on Object {
    // Skeleton-only runs without bundled fonts keep the default Ahem test font.
  }
}
