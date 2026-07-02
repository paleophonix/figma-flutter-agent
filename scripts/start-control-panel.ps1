# Start Redis (if needed), ARQ worker, and control panel API + Discord bot.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Stop-OrphanFigmaWorkers {
    # Stop stale ARQ worker processes left from prior control-panel runs.
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

function Clear-StalePipelineLocks {
    Write-Host "Clearing stale pipeline locks..."
    $keys = docker exec figma-flutter-agent-redis-1 redis-cli --scan --pattern "figma-cp:project:*" 2>$null
    foreach ($key in $keys) {
        if (-not $key) {
            continue
        }
        docker exec figma-flutter-agent-redis-1 redis-cli DEL $key | Out-Null
    }
}

Write-Host "Ensuring Redis is up..."
docker compose -f docker-compose.local.yml up -d redis | Out-Null

Stop-OrphanFigmaWorkers
Clear-StalePipelineLocks

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
