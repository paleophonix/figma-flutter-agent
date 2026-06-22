# Stop the local OpenCode serve process listening on the configured port.
# Default port is 4096 (settings.opencode_base_url / OPENCODE_BASE_URL).
param(
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-OpenCodePort {
    param([int]$ExplicitPort)

    if ($ExplicitPort -gt 0) {
        return $ExplicitPort
    }

    $baseUrl = [string]$env:OPENCODE_BASE_URL
    if (-not $baseUrl.Trim()) {
        return 4096
    }

    $uri = [Uri]$baseUrl
    if ($uri.Port -gt 0) {
        return $uri.Port
    }
    if ($uri.Scheme -eq "https") {
        return 443
    }
    return 4096
}

$listenPort = Resolve-OpenCodePort -ExplicitPort $Port
$connections = @(
    Get-NetTCPConnection -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue
)

if (-not $connections) {
    Write-Host "No OpenCode listener on port $listenPort."
    exit 0
}

$pids = $connections.OwningProcess | Sort-Object -Unique
foreach ($procId in $pids) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { "pid=$procId" }
    Write-Host "Stopping $name (PID $procId) on port $listenPort..."
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

Write-Host "OpenCode serve stopped (port $listenPort). Re-run wizard debug to start with OPENROUTER_API_KEY from .env."
