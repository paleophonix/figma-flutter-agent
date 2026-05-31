# figma-css-inspect (stub)

> **Status: Phase 3 placeholder.** The plugin is not yet built.  
> The agent's Phase 1–2 infrastructure (config + dump reader) is complete and tested.

## What this plugin will do

A Figma plugin that reads the **Inspect panel CSS** for a selected frame and
exports a JSON file in the **v1 dump format** consumed by
`figma_flutter_agent.parser.dev_mode_css`.

## Dump format v1

```json
{
  "version": 1,
  "fileKey": "<figma-file-key>",
  "exportedAt": "2026-01-15T12:00:00Z",
  "nodes": {
    "1:234": {
      "name": "Button/Primary",
      "css": {
        "background-color": "rgba(142, 151, 253, 1)",
        "border-radius": "38px",
        "font-size": "14px",
        "font-weight": "700",
        "color": "rgba(255, 255, 255, 1)",
        "clip-path": "circle(50%)"
      }
    }
  }
}
```

## How to use it (Phase 3)

1. Open the Figma file in the desktop or web app.
2. Select the top-level frame you want to export.
3. Run the **figma-css-inspect** plugin → **Export CSS dump**.
4. Save the JSON file (e.g. `dumps/sign_up.json`).
5. Reference it in `.ai-figma-flutter.yml`:

```yaml
figma:
  style_metadata:
    source: hybrid            # or dev_mode_inspect
  dev_mode:
    enabled: true
    inspect_css:
      mode: plugin_dump
      dump_path: dumps/sign_up.json
```

6. Run `poetry run figma-flutter generate …` as usual.

## Merge behaviour

| `style_metadata.source` | REST synthesis | Dump values |
|---|---|---|
| `rest_synthesis` (default) | ✅ used | ❌ ignored |
| `hybrid` | ✅ base | fills gaps only (REST wins on conflict) |
| `dev_mode_inspect` | ✅ typed fields | ✅ overrides `css_properties` |

> **Note:** The REST synthesis path (`rest_css_synthesis` in spec §23) is
> never removed.  Typed fields (`background_color`, `text_color`, etc.) always
> come from the REST API.  The dump only enriches `NodeStyle.css_properties`
> with inspect-panel values that the REST API cannot expose reliably
> (e.g. `clip-path`, `mix-blend-mode`, composite gradients).
