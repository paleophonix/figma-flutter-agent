# Initialize OpenCode submodule with sparse checkout (API-only tree).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Sparse = Join-Path $PSScriptRoot "opencode-api-sparse.txt"
$Submodule = Join-Path $Root "src\opencode"
$SubmoduleSafe = ($Submodule -replace '\\', '/')

if (-not (Test-Path $Sparse)) {
    Write-Error "Missing sparse path list: $Sparse"
}

git -C $Root submodule update --init --depth 1 src/opencode
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git -C $Submodule -c "safe.directory=$SubmoduleSafe" sparse-checkout init --no-cone
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Get-Content $Sparse | git -C $Submodule -c "safe.directory=$SubmoduleSafe" sparse-checkout set --stdin
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git -C $Submodule -c "safe.directory=$SubmoduleSafe" read-tree -mu HEAD
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "OpenCode API sparse checkout ready under $Submodule"
Write-Host "Next: cd src/opencode; bun install; bun dev serve"
