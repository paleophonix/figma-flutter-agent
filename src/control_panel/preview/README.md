# Preview release builds

## Purpose

Optional fast HTTP preview via prebuilt `flutter build web --release` artifacts
when `preview.release_build` is enabled in `.control-panel.yml`.

## Usage Example

```python
from control_panel.preview.release import build_release_previews

build_release_previews(project_dir=Path("sandbox"), job_id="abc123")
```

## LLM Context

Outputs live under `.figma-flutter/preview-release/{fixed|adaptive}/`.
`proxy_preview_request` serves these files when the flag is on; otherwise it
proxies to the colocated `flutter run -d web-server` dev preview.
