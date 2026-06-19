# Start Redis (if needed), ARQ worker, and control plane API + Discord bot.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Stop-OrphanFigmaWorkers {
    # Stop stale ARQ worker processes left from prior control-plane runs.
    $needles = @(
        "control_panel.workers.settings.WorkerSettings",
        "figma-flutter-worker"
    )
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue
    foreach ($proc in $processes) {
        $commandLine = $proc.CommandLine
        if (-not $commandLine) {
            continue
        }
        $isWorker = $false
        foreach ($needle in $needles) {
            if ($commandLine -like "*$needle*") {
                $isWorker = $true
                break
            }
        }
        if (-not $isWorker) {
            continue
        }
        Write-Host "Stopping orphan figma-flutter worker (pid $($proc.ProcessId))..."
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Ensuring Redis is up..."
docker compose -f docker-compose.control-plane.yml up -d redis | Out-Null

Stop-OrphanFigmaWorkers

$worker = Start-Process pwsh -PassThru -WindowStyle Normal -ArgumentList @(
    "-NoLogo",
    "-NoProfile",
    "-Command",
    "Set-Location '$PWD'; poetry run figma-flutter-worker"
)

try {
    Write-Host "Starting control panel (worker pid $($worker.Id))..."
    poetry run figma-flutter-control-panel
}
finally {
    if ($null -ne $worker -and -not $worker.HasExited) {
        Stop-Process -Id $worker.Id -Force -ErrorAction SilentlyContinue
    }
}
