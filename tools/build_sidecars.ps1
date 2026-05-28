# Build AST sidecar executables into tools/bin (Windows).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Sidecar = Join-Path $Root "tools\dart_ast_sidecar"
$Bin = Join-Path $Root "tools\bin"
New-Item -ItemType Directory -Force -Path $Bin | Out-Null

function Resolve-DartExecutable {
    $cmd = Get-Command dart -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $sdkRoots = @()
    if ($env:FIGMA_FLUTTER_SDK) { $sdkRoots += $env:FIGMA_FLUTTER_SDK.Trim() }
    if ($env:FLUTTER_ROOT) { $sdkRoots += $env:FLUTTER_ROOT.Trim() }

    $envFile = Join-Path $Root ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile -Encoding UTF8) {
            if ($line -match '^\s*FIGMA_FLUTTER_SDK\s*=\s*(.+)\s*$') {
                $sdkRoots += $Matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }

    foreach ($sdk in $sdkRoots | Select-Object -Unique) {
        if (-not $sdk) { continue }
        $bin = Join-Path $sdk "bin"
        foreach ($name in @("dart.bat", "dart.exe")) {
            $candidate = Join-Path $bin $name
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    return $null
}

$dart = Resolve-DartExecutable
if (-not $dart) {
    Write-Error @"
dart not found.
  1. Set FIGMA_FLUTTER_SDK in .env (e.g. FIGMA_FLUTTER_SDK=F:/src/flutter)
  2. Or for this session: `$env:Path = 'F:\src\flutter\bin;' + `$env:Path
  3. Then run: .\tools\build_sidecars.ps1
"@
}

Write-Host "Using dart: $dart"

Push-Location $Sidecar
try {
    & $dart pub get
    & $dart compile exe bin/ast_compiler.dart -o (Join-Path $Bin "ast_compiler.exe")
    Write-Host "Built $(Join-Path $Bin 'ast_compiler.exe')"
} finally {
    Pop-Location
}
