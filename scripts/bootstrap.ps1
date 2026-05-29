# One-time dev setup: deps, optional Docker golden image, doctor.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

poetry install --with dev

$buildSidecars = Join-Path $PWD "tools\build_sidecars.ps1"
if ((Test-Path $buildSidecars) -and (Get-Command dart -ErrorAction SilentlyContinue)) {
    & $buildSidecars
}

$compose = Join-Path $PWD "docker\render-capture\docker-compose.yml"
if (Get-Command docker -ErrorAction SilentlyContinue) {
    if (Test-Path $compose) {
        $versionLine = Get-Content ".flutter-version" -ErrorAction SilentlyContinue | Select-Object -First 1
        $version = if ($null -ne $versionLine -and "$versionLine".Trim()) { "$versionLine".Trim() } else { "3.29.0" }
        $env:FLUTTER_VERSION = $version
        docker compose -f $compose build golden-capture
    }
}

poetry run figma-flutter doctor
