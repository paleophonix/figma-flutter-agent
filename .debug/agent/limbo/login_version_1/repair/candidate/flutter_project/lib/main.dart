

import 'package:flutter/material.dart';
import 'package:inbox/theme/app_theme.dart';
import 'package:inbox/features/login_version_1/login_version_1_screen.dart';

// <custom-code>
// </custom-code>

/// Application entrypoint generated from Figma prototype configuration.
class FigmaFlutterApp extends StatelessWidget {
  const FigmaFlutterApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Login Version 1',
      theme: AppTheme.light(maxWebWidth: 1200),
      home: const LoginVersion1Screen(),
    );
  }
}

void main() {
  runApp(const FigmaFlutterApp());
}