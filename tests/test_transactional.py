from pathlib import Path

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.pubspec import rollback_pubspec_batch, update_pubspec
from figma_flutter_agent.generator.writing.core import DartWriter


def test_write_batch_rollback_restores_previous_content(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / "lib" / "theme" / "app_colors.dart"
    target.parent.mkdir(parents=True)
    target.write_text("class AppColors { static const old = 1; }", encoding="utf-8")

    writer = DartWriter(project_dir)
    batch = writer.write_files(
        {"lib/theme/app_colors.dart": "class AppColors { static const fresh = 2; }"}
    )
    writer.rollback_batch(batch)

    assert "old = 1" in target.read_text(encoding="utf-8")


def test_pubspec_batch_rollback_restores_previous_content(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )

    batch = update_pubspec(tmp_path, ["assets/icons/"], needs_svg=True)
    rollback_pubspec_batch(batch)

    content = pubspec.read_text(encoding="utf-8")
    assert "flutter_svg" not in content
    assert "assets/icons/" not in content


def test_pipeline_rollback_on_validation_failure(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    pubspec = project_dir / "pubspec.yaml"
    pubspec.write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )
    target = project_dir / "lib" / "main.dart"
    target.parent.mkdir(parents=True)
    target.write_text("void main() {}", encoding="utf-8")

    writer = DartWriter(project_dir)
    write_batch = None
    pubspec_batch = None
    try:
        write_batch = writer.write_files({"lib/main.dart": "void main() { broken"})
        pubspec_batch = update_pubspec(project_dir, ["assets/icons/"])
        raise GenerationError("analyze failed")
    except GenerationError:
        writer.rollback_batch(write_batch)
        rollback_pubspec_batch(pubspec_batch)

    assert target.read_text(encoding="utf-8") == "void main() {}"
    assert "flutter_svg" not in pubspec.read_text(encoding="utf-8")
