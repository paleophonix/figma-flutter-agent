# AST sidecar binaries

Build on **each OS** (native AOT; not downloaded from the internet):

| OS | Script | Output |
|----|--------|--------|
| Windows | `.\tools\build_sidecars.ps1` | `ast_compiler.exe` |
| Linux | `./tools/build_sidecars.sh` | `ast_compiler-linux` |
| macOS | `./tools/build_sidecars.sh` | `ast_compiler-macos` |

Requires Dart (Flutter SDK): `FIGMA_FLUTTER_SDK` in `.env` or `dart` on `PATH`.

Override at runtime: `FIGMA_AST_COMPILER_PATH=/path/to/binary`.

When the prebuilt for the current OS is missing, Python applies the same P0 rules in-process and logs a warning.

**Cross-compile (optional):** from a machine with Dart 3+, you can target another OS without running the shell script there, e.g. Linux artifact on Windows:

```bash
dart compile exe --target-os=linux --target-arch=x64 \
  -o tools/bin/ast_compiler-linux \
  tools/dart_ast_sidecar/bin/ast_compiler.dart
```

Run `dart compile exe -h` for supported `--target-os` / `--target-arch` pairs.
