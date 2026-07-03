# Technical notes & spec interpretation

## Style metadata (“Dev Mode”)

The agent does **not** call the separate Figma Dev Mode API. Style metadata is **synthesized from REST** nodes + Styles API (`rest_css_synthesis` in spec23). Expect gaps: no plugin handoff URLs, some enterprise-only fields absent, `SCALE` constraints approximated in codegen.

Optional Dev Mode enrichment (config only; plugin stub):

```yaml
figma:
  style_metadata:
    source: hybrid          # rest_synthesis (default) | hybrid | dev_mode_inspect
  dev_mode:
    enabled: true
    inspect_css:
      mode: plugin_dump
      dump_path: dumps/my_screen.json
```

| `source` | REST synthesis | Plugin dump |
|---|---|---|
| `rest_synthesis` | ✅ (default) | ❌ ignored |
| `hybrid` | ✅ base | fills gaps only |
| `dev_mode_inspect` | ✅ typed fields | overrides `css_properties` |

Plugin stub: `tools/figma_css_inspect/README.md`.

## Incremental sync

File-hash sync with `layout_region_hash` + `cluster_hashes`. Cluster edits rewrite `lib/widgets/<widget>.dart`; layout edits rewrite the screen layout file. Corrupt `snapshot.json` is quarantined to `snapshot.json.corrupt` (`sync.fail_on_corrupt_snapshot: true` fails fast in production).

Unchanged design tree hash → skip LLM regen. `--force-llm-regen` after prompt/model changes. `regen_llm_on_token_change: true` for token-only Figma updates.

Custom code: `// <custom-code>` zones; `strict_preservation` refuses write on orphan edits.

## LLM codegen

Keys in `.env`: `LLM_PROVIDER`, `LLM_GENERATE_MODEL`, provider key. Providers: `anthropic`, `openai`, `openrouter`, `google`, `google_aistudio`.

With `LLM_REQUIRE_STRICT_JSON_SCHEMA=true`, production expects strict JSON schema support (`anthropic`, `openai`). Dev providers may log `structured_output_fallback`.

Optional loops in YAML: `llm_repair_after_analyze`, `llm_visual_refine`.

## Other limitations

- **Figma quota:** prefer `batch dump-file` + `batch generate` + `run`
- **Sync:** `--no-sync` forces full rewrite; `--allow-stubs` for LLM failure placeholders
- **Variables API:** 403 → paints/styles fallback
- **Responsive:** breakpoints in `app_layout.dart` — 480 / 768 / 1024; reflow above 480px
- **Animations:** prototype navigation transitions only; Lottie post-MVP
- **Visual QA:** golden tests compare Flutter renders; Figma reference PNG needs live fetch
- **WebP:** opt-in via `assets.webp` (Pillow)
- Secrets masked in verbose logs

## Spec interpretation (MVP deltas)

| Topic | Production behavior |
|-------|---------------------|
| **§5.1 styles** | REST/CSS synthesis, not Dev Mode API |
| **§7.3 responsive** | `LayoutBuilder` reflow, four-band grids, sidebar chrome, `max_web_width: 1200` |
| **§10 AI codegen** | LLM screen IR + emitter; cached IR / fixtures for offline validation |
| **§16–17 preservation** | `// <custom-code>` + region-aware sync |
| **§9 quality** | `quality.enforce_spec9_gates`; production profile enables depth/contrast/preservation |
| **§19 IDE** | CLI wizard + `.vscode/*` (no marketplace plugins) |
| **§21.2 animation** | Prototype transitions; `animations.json` in debug bundle |
| **§21.4 AI UX** | `ai_ux.json` + pipeline warnings |
| **§3 state management** | `none` default; `riverpod` / `bloc` / `provider` in YAML |
| **§7.6 variables** | Best-effort fetch; 403 fallback |
| **§9 / §23 production profile** | On `generate` unless `--allow-dev-profile` |

CI: `demo-signoff --strict --signoff-gates`. Visual QA: `--visual-qa` or YAML `dark_mode` / `validation` flags.
