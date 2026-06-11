# Semantic widget Jinja2 templates

## Purpose

Dart widget fragments for MVP semantic `WidgetIrKind` values emitted via `generator/ir/semantic_emit.py`.

## Usage Example

Templates are rendered by `emit_semantic_widget()`; do not call Jinja2 directly from application code.

## LLM Context

When the model sets `kind` to a semantic MVP value (`chip_choice`, `button_filled`, …), the IR expression emitter selects the matching `*.dart.j2` file in this directory instead of Python layout string builders. Template context includes `style` from `build_style_context()` and optional `payload` fields.
