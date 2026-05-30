# Offline release gate (Windows). Requires Poetry on PATH.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

poetry run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run mypy src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run figma-flutter demo-signoff --strict --signoff-gates
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run figma-flutter fixture-ir-validate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$buildSidecars = Join-Path $PSScriptRoot "..\tools\build_sidecars.ps1"
if (Test-Path $buildSidecars) {
    & $buildSidecars
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

poetry run pytest -q -m "not live_figma"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($env:FIGMA_SIGNOFF_DOCKER -eq "1") {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "FIGMA_SIGNOFF_DOCKER=1 but docker not found; skipping docker pytest"
        exit 1
    }
    $compose = Join-Path $PSScriptRoot "..\docker\render-capture\docker-compose.yml"
    docker compose -f $compose build golden-capture
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    docker compose -f $compose run --rm golden-capture flutter --version
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Sign-off OK"
