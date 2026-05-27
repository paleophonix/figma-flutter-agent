# Visual QA offline gate (Windows): golden/visual pytest + demo-signoff --visual-qa profile.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

poetry run pytest -q tests/test_golden_generation.py tests/test_visual_qa_profile.py tests/test_visual_qa_compare.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

poetry run figma-flutter demo-signoff --strict --signoff-gates --visual-qa
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Visual QA sign-off OK"
