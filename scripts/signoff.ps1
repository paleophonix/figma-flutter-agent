# Offline release gate (Windows). Requires Poetry on PATH.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

poetry run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

New-Item -ItemType Directory -Force -Path logs/lint | Out-Null
poetry run python scripts/lint_dart_in_python.py --write-burndown logs/lint/dart_debt_burndown.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run mypy src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run figma-flutter demo-signoff --strict --signoff-gates
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run figma-flutter fixture-ir-validate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run figma-flutter fidelity validate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

New-Item -ItemType Directory -Force -Path logs/semantics | Out-Null
poetry run figma-flutter semantics corpus-gate --write-report logs/semantics/w1_classification_gate.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run python scripts/semantics_legacy_burndown.py --write-report logs/semantics/legacy_burndown.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($env:FIGMA_GEOMETRY_SIGNOFF -ne "0") {
    $geoScreens = $env:FIGMA_GEOMETRY_SIGNOFF_SCREENS
    if ($geoScreens) {
        foreach ($screen in ($geoScreens -split ',')) {
            $id = $screen.Trim()
            if (-not $id) { continue }
            poetry run figma-flutter fixture-geometry-check --screen $id
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
    } else {
        poetry run figma-flutter fixture-geometry-check
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

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
