# Regenerate golden PNG baselines for tests/fixtures/screens.yaml (Docker preferred).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$env:FIGMA_GOLDEN_RUNTIME = "docker"

$compose = Join-Path $PWD "tools\render-capture\docker-compose.yml"
if (Get-Command docker -ErrorAction SilentlyContinue) {
    if (Test-Path $compose) {
        $versionLine = Get-Content ".flutter-version" -ErrorAction SilentlyContinue | Select-Object -First 1
        $version = if ($null -ne $versionLine -and "$versionLine".Trim()) { "$versionLine".Trim() } else { "3.29.0" }
        $env:FLUTTER_VERSION = $version
        docker compose -f $compose build golden-capture
    }
}

poetry run python scripts/generate_fixture_goldens.py --update-goldens --golden-runtime docker
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Golden baselines updated under tests/fixtures/golden/png/docker/"
