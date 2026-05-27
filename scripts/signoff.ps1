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

poetry run pytest -q -m "not live_figma"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Sign-off OK"
