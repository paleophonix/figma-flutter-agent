"""Generated screen shell construction."""

from __future__ import annotations

import re

_GENERATED_SCREEN_SHELL_RE = re.compile(
    r"(/// Responsive shell injected[\s\S]*?^class GeneratedScreenShell\b[\s\S]*?^\})",
    re.MULTILINE,
)


def _extract_generated_screen_shell(prior: str) -> str:
    match = _GENERATED_SCREEN_SHELL_RE.search(prior)
    return match.group(1).strip() if match is not None else ""


def _screen_shell_block_for_fallback(*, max_web_width: int) -> str:
    """Return the canonical ``GeneratedScreenShell`` for emit-gate recovery.

    Parse-gate fallback must not reuse shell text from the failing source: chunked AST
    and delimiter repair often corrupt ``GeneratedScreenShell`` while the screen body is
    replaced separately.
    """
    return f"{_default_generated_screen_shell(max_web_width=max_web_width)}\n\n"


def _default_generated_screen_shell(*, max_web_width: int) -> str:
    return f"""/// Responsive shell injected by the generator for web/tablet max width.
class GeneratedScreenShell extends StatelessWidget {{
  const GeneratedScreenShell({{
    super.key,
    required this.child,
    this.maxWebWidth = {max_web_width},
  }});

  final Widget child;
  final double maxWebWidth;

  static final double _artboardPreviewWidth = double.tryParse(
        const String.fromEnvironment('FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH'),
      ) ??
      0;
  static final double _artboardPreviewHeight = double.tryParse(
        const String.fromEnvironment('FIGMA_FLUTTER_ARTBOARD_PREVIEW_HEIGHT'),
      ) ??
      0;
  static final bool _artboardCaptureMode =
      const String.fromEnvironment('FIGMA_FLUTTER_ARTBOARD_CAPTURE_MODE', defaultValue: '') == '1';
  static const bool _browserViewportFrame = bool.fromEnvironment(
    'FIGMA_FLUTTER_BROWSER_VIEWPORT_FRAME',
    defaultValue: false,
  );

  @override
  Widget build(BuildContext context) {{
    if (_artboardPreviewWidth > 0 && _artboardPreviewHeight > 0 && _artboardCaptureMode) {{
      return Align(
        alignment: Alignment.topLeft,
        child: ClipRect(
          child: SizedBox(
            width: _artboardPreviewWidth,
            height: _artboardPreviewHeight,
            child: ColoredBox(
              color: Theme.of(context).scaffoldBackgroundColor,
              child: child,
            ),
          ),
        ),
      );
    }}
    final layout = Theme.of(context).extension<AppLayoutExtension>();
    final resolvedMaxWidth = layout?.maxWebWidth ?? maxWebWidth;
    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      body: LayoutBuilder(
        builder: (context, constraints) {{
          final media = MediaQuery.sizeOf(context);
          final width = constraints.maxWidth.isFinite && constraints.maxWidth > 0
              ? constraints.maxWidth
              : media.width;
          final horizontalPadding = AppBreakpoints.horizontalPadding(width);
          final contentMaxWidth = AppBreakpoints.contentMaxWidth(width, resolvedMaxWidth);
          final framedChild = _browserViewportFrame
              ? DecoratedBox(
                  decoration: BoxDecoration(
                    border: Border.all(color: Color(0xFF808080), width: 1.0),
                  ),
                  child: child,
                )
              : child;
          return Align(
            alignment: Alignment.topCenter,
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: contentMaxWidth),
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
                child: framedChild,
              ),
            ),
          );
        }},
      ),
    );
  }}
}}"""
