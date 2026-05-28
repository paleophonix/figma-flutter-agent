# Regenerate golden PNG baselines for tests/fixtures/screens.yaml (Docker preferred).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$env:FIGMA_GOLDEN_RUNTIME = "docker"

$compose = Join-Path $PWD "docker\render-capture\docker-compose.yml"
if (Get-Command docker -ErrorAction SilentlyContinue) {
    if (Test-Path $compose) {
        $version = (Get-Content ".flutter-version" -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
        if (-not $version) { $version = "3.29.0" }
        $env:FLUTTER_VERSION = $version
        docker compose -f $compose build golden-capture
    }
}

poetry run python scripts/generate_fixture_goldens.py --golden-runtime docker
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Golden baselines updated under tests/fixtures/golden/png/docker/"
