# Manual E2E helper (Windows). Set variables, then run sections interactively.
# Does NOT read secrets from repo — pass FIGMA_URL and PROJECT_DIR yourself.
param(
    [Parameter(Mandatory = $true)]
    [string]$FigmaUrl,
    [Parameter(Mandatory = $true)]
    [string]$ProjectDir
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "=== Offline sign-off ===" -ForegroundColor Cyan
& "$PSScriptRoot\signoff.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Live check ===" -ForegroundColor Cyan
poetry run figma-flutter live-check --figma-url $FigmaUrl --dump --project-dir $ProjectDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Production generate ===" -ForegroundColor Cyan
poetry run figma-flutter generate --figma-url $FigmaUrl --project-dir $ProjectDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Flutter analyze (in project) ===" -ForegroundColor Cyan
Push-Location $ProjectDir
dart format .
flutter analyze
$analyzeExit = $LASTEXITCODE
Pop-Location
if ($analyzeExit -ne 0) { exit $analyzeExit }

Write-Host "`nE2E helper finished. Complete runtime smoke manually: cd $ProjectDir; flutter run -d chrome" -ForegroundColor Green
Write-Host "Record results in tests/README.md (Manual E2E acceptance section)"
