# Pack one repair worktree into a single merge-review bundle (stdout or file).
# Usage:
#   .\scripts\repair-merge-pack.ps1
#   .\scripts\repair-merge-pack.ps1 -CaseId 57d449fda0bc
#   .\scripts\repair-merge-pack.ps1 -OutFile .temp\merge-pack.md

param(
    [string]$CaseId = "",
    [string]$RepoRoot = "",
    [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    param([string]$Hint)
    if ($Hint -and (Test-Path $Hint)) {
        return (Resolve-Path $Hint).Path
    }
    $here = Split-Path -Parent $PSScriptRoot
    if (Test-Path (Join-Path $here ".git")) {
        return $here
    }
    throw "Cannot resolve agent repo root; pass -RepoRoot"
}

function Find-Worktree {
    param([string]$Root, [string]$Id)
    $parents = @(
        (Join-Path $Root ".worktrees"),
        (Join-Path $Root ".repair\worktrees")
    )
    $existing = @($parents | Where-Object { Test-Path $_ })
    if ($existing.Count -eq 0) {
        throw "No .worktrees (or legacy .repair/worktrees) under $Root"
    }
    if ($Id) {
        foreach ($parent in $existing) {
            $path = Join-Path $parent $Id
            if (Test-Path $path) {
                return (Resolve-Path $path).Path
            }
        }
        throw "Worktree not found for case id: $Id"
    }
    $latest = $null
    foreach ($parent in $existing) {
        $candidate = Get-ChildItem $parent -Directory -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($candidate -and (-not $latest -or $candidate.LastWriteTime -gt $latest.LastWriteTime)) {
            $latest = $candidate
        }
    }
    if (-not $latest) {
        throw "No repair worktrees found under $($existing -join ', ')"
    }
    return $latest.FullName
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return $null
    }
    return Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Git-Diff {
    param([string]$Worktree)
    $safe = "safe.directory=$($Worktree.Replace('\', '/'))"
    $stat = & git -c $safe -C $Worktree diff --stat HEAD 2>&1
    $body = & git -c $safe -C $Worktree diff HEAD -- src/ tests/ 2>&1
    return @{ Stat = ($stat | Out-String).Trim(); Body = ($body | Out-String).Trim() }
}

$repo = Resolve-RepoRoot -Hint $RepoRoot
$worktree = Find-Worktree -Root $repo -Id $CaseId
$caseId = Split-Path $worktree -Leaf
$stateDir = Join-Path $worktree ".repair\state"
$manifest = Read-JsonFile (Join-Path $worktree ".repair\manifest.json")
$plan = Read-JsonFile (Join-Path $stateDir "plan.json")
$repair = Read-JsonFile (Join-Path $stateDir "repair.json")
$check = Read-JsonFile (Join-Path $stateDir "check.json")
$diff = Git-Diff -Worktree $worktree

$touched = @()
if ($repair -and $repair.filesTouched) {
    $touched = @($repair.filesTouched)
}

$lines = @(
    "# Repair merge pack",
    "",
    "## worktree",
    "- case_id: $caseId",
    "- path: $worktree",
    "- feature: $($manifest.feature)",
    "- project: $($manifest.project)",
    "- case_mode: $($manifest.case_mode)",
    "",
    "## repair outcome",
    "- scope_passed: $($repair.scope.passed)",
    "- files_touched: $(if ($touched.Count) { $touched -join ', ' } else { '(none)' })",
    "- check_passed: $($check.passed)",
    "- stop_class: $($check.failure_class)",
    "",
    "## plan steps"
)

if ($plan -and $plan.steps) {
    foreach ($step in $plan.steps) {
        $law = $step.lawId
        $targets = @($step.targetFiles) -join ", "
        $tests = @()
        foreach ($t in $step.tests) {
            if ($t.file) { $tests += $t.file }
        }
        $testList = ($tests -join ", ")
        $lines += "- **$law** -> targets: $targets; tests: $testList"
    }
} else {
    $lines += "- (plan.json missing)"
}

$lines += @(
    "",
    "## git diff --stat",
    "``````",
    $(if ($diff.Stat) { $diff.Stat } else { "(empty)" }),
    "``````",
    "",
    "## git diff src tests",
    "``````diff",
    $(if ($diff.Body) { $diff.Body } else { "# no tracked changes under src/ or tests/" }),
    "``````",
    ""
)

$text = ($lines -join "`n")

if ($OutFile) {
    $outDir = Split-Path -Parent $OutFile
    if ($outDir -and -not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    }
    Set-Content -Path $OutFile -Value $text -Encoding UTF8
    Write-Output $OutFile
} else {
    Write-Output $text
}
