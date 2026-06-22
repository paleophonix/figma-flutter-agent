# Remove local repair git worktrees and delete all repair/* branches.
# Does not touch remote branches or non-repair local branches (e.g. main).
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-GitBranchName {
    param([string]$Line)
    return ($Line.Trim() -replace '^[\*\+]\s+', '')
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
    if ($currentBranch -ne "main") {
        if ($DryRun) {
            Write-Host "[dry-run] Would run: git checkout main"
        } else {
            git checkout main | Out-Host
        }
    }

    $worktreeDirs = @()
    foreach ($parentName in @(".worktrees", ".repair/worktrees")) {
        $parent = Join-Path $repoRoot $parentName
        if (Test-Path -LiteralPath $parent) {
            $worktreeDirs += Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue
        }
    }

    foreach ($dir in $worktreeDirs) {
        $branchName = "repair/$($dir.Name)"
        if ($DryRun) {
            Write-Host "[dry-run] Would remove worktree: $($dir.FullName) and branch: $branchName"
            continue
        }
        git worktree remove --force $dir.FullName 2>&1 | Out-Host
        if (git branch --list $branchName) {
            git branch -D $branchName 2>&1 | Out-Host
        }
    }

    if ($DryRun) {
        Write-Host "[dry-run] Would run: git worktree prune"
    } else {
        git worktree prune | Out-Host
    }

    $orphanBranches = git branch --list "repair/*" | ForEach-Object { Get-GitBranchName $_ }
    $removed = 0
    foreach ($branch in $orphanBranches) {
        if (-not $branch) {
            continue
        }
        if ($DryRun) {
            Write-Host "[dry-run] Would delete branch: $branch"
            $removed++
            continue
        }
        git branch -D $branch 2>&1 | Out-Host
        $removed++
    }

    Write-Host ""
    Write-Host "Repair cleanup complete. Branches removed: $removed. Remaining:"
    git branch
    Write-Host ""
    Write-Host "Worktrees:"
    git worktree list
}
finally {
    Pop-Location
}
