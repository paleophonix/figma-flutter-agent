# Discord preview companion

Register the `figma-flutter://` URL protocol on Windows to point at:

```text
python -m control_panel.companion.daemon --url "%1"
```

The job runner writes `.figma-flutter/preview-session.json` into the user's Flutter
project with token hash and port assignments.

Manual launch:

```bash
poetry run python -m control_panel.companion.daemon \
  --project-dir /path/to/user/project \
  --mode fixed \
  --token "<token-from-discord-message>"
```
