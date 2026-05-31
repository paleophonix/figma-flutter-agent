"""One-off: annotate terminal log excerpt into docs markdown table."""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(
    r"C:\Users\Home\.cursor\projects\e-dev-figma-flutter-agent\uploads"
    r"\_e-dev-figma-flutter-agent_39-L17-L817-0.txt"
)
OUT = Path(__file__).resolve().parents[1] / "docs" / "wizard-launch-sign-up-log-line-by-line.md"
T0 = 23


def comment_for(line: str) -> str:
    if not line.strip():
        return "Пустая строка в логе."
    if line.startswith("Run mode:"):
        return "Визард: режим launch, кэш dump."
    if line.startswith("Screen: sign_up"):
        return "Выбранный экран/feature."
    if line.startswith("Dump: OK"):
        return "Сырой Figma JSON на диске — fetch из API не нужен."
    if "main.dart wired" in line:
        return "В main.dart другой screen — возможна перезапись при write."
    if line.startswith("Icons:"):
        return "Статус экспорта иконок (не блокер)."
    if "Codegen: LLM" in line:
        return "Тело sign_up_screen от LLM; fail-fast без deterministic fallback в plan."
    if line.startswith("Device:"):
        return "Целевое устройство flutter run."
    if "Launching Flutter on chrome after sync" in line:
        return "После sync: run_pipeline, затем flutter run."
    if "Generation mode: llm" in line:
        return "Пайплайн: LLM screen body, llm_fallback_to_deterministic=False."
    if "Pipeline run started" in line:
        return "Старт run_pipeline."
    if "Dev Mode CSS dump loaded" in line:
        return "Подключён css_dump.json."
    if "Stage fetch started" in line:
        return "Стадия fetch."
    if "Loaded cached Figma dump" in line:
        return "Чтение sign_up_layout.json."
    if "Stage fetch completed" in line:
        return "Fetch завершён."
    if "Stage parse started" in line:
        return "Стадия parse."
    if "Dev Mode CSS dump active" in line:
        return "CSS override при парсинге."
    if "Stage parse completed" in line:
        return "Parse завершён."
    if "Stage fonts started" in line:
        return "Стадия fonts."
    if "Stage fonts completed" in line:
        return "Fonts завершены."
    if "Stage analyze started" in line:
        return "Analyze дизайн-дерева (не dart analyze)."
    if "Stage analyze completed" in line and "dart" not in line.lower():
        return "Analyze дизайна завершён."
    if "Saved processed design tree" in line:
        return "Dump processed дерева."
    if "AI UX report" in line:
        return "Отчёт UX."
    if "animation manifest" in line:
        return "Манифест анимаций."
    if "Stage llm started" in line:
        return "Стадия LLM."
    if "gemini-3.5-flash is not in the recommended" in line:
        return "Модель не в whitelist (не фатально)."
    if "structured_output_fallback" in line:
        return "JSON schema non-strict для Google."
    if "Using LLM provider google" in line:
        return "Параметры LLM."
    if "Attached Figma reference PNG" in line:
        return "PNG в промпте."
    if "IR presence normalized: +50" in line:
        return "Добавлены узлы в IR."
    if "IR presence inserted 50 nodes (cap 40)" in line:
        return "Cap превышен — IR раздут."
    if "Stage llm completed" in line:
        return "LLM завершён (~44 с)."
    if "Stage plan started" in line:
        return "Стадия plan."
    if "Subtree plan: checking" in line:
        return "План subtree-виджетов."
    if "1 widget(s) need render" in line:
        return "Один виджет к рендеру."
    if "Rendering 1 subtree" in line:
        return "Рендер subtree."
    if "Subtree widgets rendered" in line:
        return "Subtree готов."
    if "Pruned 4 decorative" in line:
        return "Убраны декоративные Vector."
    if "generating layout file for sign_up" in line:
        return "Детерминированный sign_up_layout.dart."
    if "invalid Dart syntax: Unexpected" in line and "screen_code" in line:
        return "LLM screen_code битый (лишняя )."
    if "Repaired Dart delimiters in LLM screen_code" in line:
        return "Починка скобок."
    if "Ambient background reconcile produced invalid" in line:
        return "Патч ambient отклонён."
    if "clean-tree text sync broke" in line:
        return "Синхронизация текста отклонена."
    if "final planned_dart reconcile" in line:
        return "Финальная reconcile."
    if "reconcile_planned_dart_files starting" in line:
        return "Старт reconcile (13 файлов)."
    if "Planned Dart incremental reconcile" in line:
        return "Incremental AST."
    if "Planned reconcile phase:" in line:
        return f"Фаза: {line.split('phase:')[-1].strip()}."
    if "Planned Dart reconcile starting (13 files" in line:
        return "AST sidecar на файлы."
    if "AST sidecar: lib/features/sign_up" in line:
        return "AST: sign_up_screen.dart."
    if "AST reconcile 2.3s" in line:
        return "Sidecar screen 2.3 с."
    if "screen tree text and flex broke" in line:
        return "Патч flex отклонён."
    if "AST sidecar reconcile backend" in line:
        return "Backend subprocess."
    if "Planned Dart reconcile finished" in line:
        return "Reconcile завершён."
    if "Stage plan completed" in line:
        return "Plan готов."
    if "_guard_orphan_edits" in line:
        m = re.search(r"in (\S+)", line)
        path = m.group(1) if m else "файл"
        if "sign_up_screen.dart" in line and "sign_up_layout.dart" in line:
            return "orphan_edits после fallback stub — warning."
        if "main.dart" in path:
            return "orphan_edits main — warning."
        return f"orphan_edits {path} — warning, не блокер."
    if "Formatting 13 Dart file(s)" in line:
        return "Batch dart format."
    if "Running dart format" in line:
        return "Subprocess dart format."
    if "exit code 65" in line:
        return "FAIL: непарсируемый Dart."
    if "exit code 0" in line and "dart format" in line:
        return "OK: format прошёл."
    if "dart format: 13/13 ok" in line:
        return "Все файлы OK."
    if "fallback_unparseable_screens_to_layout" in line:
        return "FALLBACK: SignUpLayout + shell stub."
    if "Stage validate started" in line:
        return "validate_generated_dart."
    if "Stage validate completed" in line:
        return "Validate OK."
    if "Stage llm_repair started" in line:
        return "llm_repair / spec23."
    if "Using LLM repair model" in line:
        return "Модель repair."
    if "pub get --offline" in line and "Running" in line:
        return "pub get."
    if "pub get --offline finished" in line:
        return "pub get OK."
    if "Running dart analyze (generated)" in line and "finished" not in line:
        return "dart analyze (spec23)."
    if "dart analyze (generated) finished" in line:
        return "analyze OK."
    if "Skipping pub get" in line:
        return "pub get skip."
    if "Stage llm_repair completed" in line:
        return "llm_repair OK."
    if "visual_refine started" in line.lower():
        return "visual_refine."
    if "Visual refine skipped" in line:
        return "refine выключен."
    if "visual_refine completed" in line.lower():
        return "refine done."
    if "Saved debug Dart bundle" in line:
        return "debug bundle."
    if "Stage write started" in line:
        return "Write в demo_app."
    if "dart analyze (generated) passed for" in line:
        return "analyze demo_app OK."
    if "Write stage complete" in line:
        return "13 файлов записано."
    if "Stage write completed" in line:
        return "Write done."
    if "No FILL-sized nodes" in line:
        return "warning FILL."
    if "No prototype navigation" in line:
        return "warning nav links."
    if "delegates to SignUpLayout" in line:
        return "итог: layout delegate, не LLM UI."
    if "Generated screen sign_up via cached dump" in line:
        return "успех визарда."
    if "Running flutter pub get in" in line:
        return "pub get перед run."
    if line.startswith("Resolving") or line.startswith("Downloading"):
        return "вывод pub get."
    if "Got dependencies" in line:
        return "pub get OK."
    if "flutter outdated" in line:
        return "info."
    if "Launching flutter run on chrome" in line:
        return "flutter run."
    if "Launching lib" in line and "Chrome" in line:
        return "web build."
    if "Waiting for connection" in line:
        return "ожидание Chrome."
    if line.startswith("Flutter run key"):
        return "справка hot keys."
    if line.strip().startswith("r Hot") or line.strip().startswith("R Hot"):
        return "hot reload/restart."
    if "Hot reload" in line or "Hot restart" in line or "List all available" in line:
        return "команда flutter run."
    if "Detach" in line or "Clear the screen" in line or line.strip().startswith("q Quit"):
        return "команда flutter run."
    if "debug service" in line.lower():
        return "debug WS."
    if "Dart VM Service" in line:
        return "VM URL."
    if "DevTools" in line:
        return "DevTools URL."
    if line.strip() == "Starting":
        return "Flutter framework (обрезано)."
    return "—"


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    rows = [
        "# Построчный лог: `figma-flutter -i` launch `sign_up`",
        "",
        "Источник: `terminals/39.txt` **T-23 … T-823**.",
        "",
        "Краткая сводка: [wizard-launch-sign-up-log-annotated.md](./wizard-launch-sign-up-log-annotated.md).",
        "",
        "| T | L | Лог (сокращ.) | Комментарий |",
        "|---:|---:|---|---|",
    ]
    for i, line in enumerate(lines, start=1):
        t = T0 + i - 1
        log = line.replace("|", "\\|").replace("\n", " ")
        if len(log) > 100:
            log = log[:97] + "…"
        rows.append(f"| {t} | {i} | `{log}` | {comment_for(line)} |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} rows -> {OUT}")


if __name__ == "__main__":
    main()
