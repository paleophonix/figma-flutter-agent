

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:inbox/theme/app_colors.dart';
import 'package:inbox/theme/app_spacing.dart';

// <custom-code>
// </custom-code>

// <custom-code>
// </custom-code>

class BackWidget extends StatelessWidget {
  const BackWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(child: SvgPicture.asset('assets/icons/back_103_584.svg', width: 45.0, height: 45.0, fit: BoxFit.fill));
  }
}