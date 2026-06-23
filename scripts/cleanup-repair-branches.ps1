# Remove local repair git worktrees and delete all repair/* branches.
# Cleans physical .worktrees/, orphaned .git/worktrees/* metadata, and stale repair/* refs.
# Does not touch remote branches or non-repair local branches (e.g. main).
param(
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$RepairCaseIdPattern = '^\d{4}-\d{4}-'
$RepairBranchPrefix = "repair/"

function Get-GitBranchName {
    param([string]$Line)
    return ($Line.Trim() -replace '^[\*\+]\s+', '')
}

function Test-RepairCaseId {
    param([string]$Name)
    return $Name -match $RepairCaseIdPattern
}

function Test-PathSafe {
    param([Parameter(Mandatory)][string]$Path)

    try {
        return Test-Path -LiteralPath $Path -ErrorAction Stop
    } catch {
        return $false
    }
}

function Invoke-Git {
    param([Parameter(Mandatory)][string[]]$GitArgs)

    $output = & git @GitArgs 2>&1
    $code = $LASTEXITCODE
    if ($output) {
        $output | ForEach-Object { Write-Host $_ }
    }
    return $code
}

function Remove-DirectoryForce {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-PathSafe -Path $Path)) {
        return $true
    }
    try {
        cmd /c "attrib -R /S /D `"$Path\*`"" 2>$null | Out-Null
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        return $true
    } catch {
        Write-Warning "Could not remove '$Path': $($_.Exception.Message). Close Cursor/IDE and rerun."
        return $false
    }
}

function Get-RegisteredWorktrees {
    $entries = @()
    $raw = & git worktree list --porcelain 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "git worktree list failed."
        return $entries
    }

    $current = @{}
    foreach ($line in $raw) {
        $text = [string]$line
        if ($text.StartsWith("worktree ")) {
            if ($current.Count -gt 0) {
                $entries += [pscustomobject]$current
            }
            $current = @{ Path = $text.Substring(9).Trim() }
            continue
        }
        if ($text.StartsWith("branch ")) {
            $current.Branch = $text.Substring(7).Trim() -replace '^refs/heads/', ''
        }
    }
    if ($current.Count -gt 0) {
        $entries += [pscustomobject]$current
    }
    return $entries
}

function Get-RepairWorktreeRoots {
    param([string]$RepoRoot)

    $paths = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

    foreach ($entry in Get-RegisteredWorktrees) {
        $branch = [string]$entry.Branch
        $path = [string]$entry.Path
        if (-not $path) {
            continue
        }
        if ($branch.StartsWith($RepairBranchPrefix) -or (Test-RepairCaseId -Name (Split-Path -Leaf $path))) {
            [void]$paths.Add($path)
        }
    }

    foreach ($parentName in @(".worktrees", ".repair/worktrees")) {
        $parent = Join-Path $RepoRoot $parentName
        if (-not (Test-PathSafe -Path $parent)) {
            continue
        }
        foreach ($dir in Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue) {
            [void]$paths.Add($dir.FullName)
        }
    }

    return @($paths)
}

function Remove-RepairWorktree {
    param(
        [Parameter(Mandatory)][string]$WorktreePath,
        [switch]$DryRun
    )

    $leaf = Split-Path -Leaf $WorktreePath
    $branchName = "$RepairBranchPrefix$leaf"

    if ($DryRun) {
        Write-Host "[dry-run] Would remove worktree: $WorktreePath (branch: $branchName)"
        return
    }

    if (Test-PathSafe -Path $WorktreePath) {
        $code = Invoke-Git -GitArgs @("worktree", "remove", "--force", $WorktreePath)
        if ($code -ne 0) {
            Write-Warning "git worktree remove failed for $WorktreePath; removing directory directly."
            Remove-DirectoryForce -Path $WorktreePath | Out-Null
        }
    }

    if (git branch --list $branchName 2>$null) {
        Invoke-Git -GitArgs @("branch", "-D", $branchName) | Out-Null
    }
}

function Remove-OrphanWorktreeMetadata {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [switch]$DryRun
    )

    $metaRoot = Join-Path $RepoRoot ".git/worktrees"
    if (-not (Test-PathSafe -Path $metaRoot)) {
        return
    }

    foreach ($metaDir in Get-ChildItem -LiteralPath $metaRoot -Directory -ErrorAction SilentlyContinue) {
        $gitdirFile = Join-Path $metaDir.FullName "gitdir"
        $linkedGitFile = $null
        $gitdirLocked = $false
        if (Test-PathSafe -Path $gitdirFile) {
            try {
                $linkedGitFile = (Get-Content -LiteralPath $gitdirFile -Raw -ErrorAction Stop).Trim()
            } catch {
                $gitdirLocked = $true
                Write-Warning "Cannot read $gitdirFile (likely locked by Cursor/IDE): $($_.Exception.Message)"
            }
        }

        if ($gitdirLocked) {
            continue
        }

        $worktreeRoot = $null
        if ($linkedGitFile) {
            $worktreeRoot = Split-Path -Parent $linkedGitFile
        }

        $isRepairMeta = Test-RepairCaseId -Name $metaDir.Name
        $linkedMissing = -not $linkedGitFile -or -not (Test-PathSafe -Path $linkedGitFile)
        $worktreeMissing = -not $worktreeRoot -or -not (Test-PathSafe -Path $worktreeRoot)
        $underAgentWorktrees = $false
        if ($worktreeRoot) {
            $underAgentWorktrees = (
                $worktreeRoot -match '[\\/]\.worktrees[\\/]' -or
                $worktreeRoot -match '[\\/]\.repair[\\/]worktrees[\\/]'
            )
        }

        $shouldRemove = $false
        if ($isRepairMeta -and ($linkedMissing -or $worktreeMissing)) {
            $shouldRemove = $true
        } elseif ($underAgentWorktrees -and $linkedMissing) {
            $shouldRemove = $true
        }

        if (-not $shouldRemove) {
            continue
        }

        if ($DryRun) {
            Write-Host "[dry-run] Would remove orphaned worktree metadata: $($metaDir.Name)"
            continue
        }

        if (Remove-DirectoryForce -Path $metaDir.FullName) {
            Write-Host "Removed orphaned worktree metadata: $($metaDir.Name)"
        }
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    if (-not (Test-PathSafe -Path (Join-Path $repoRoot ".git"))) {
        throw "Not a git repository: $repoRoot"
    }

    $currentBranch = (git rev-parse --abbrev-ref HEAD 2>$null).Trim()
    if ($currentBranch -and $currentBranch -ne "main" -and $currentBranch -ne "HEAD") {
        if ($DryRun) {
            Write-Host "[dry-run] Would run: git checkout main"
        } else {
            Invoke-Git -GitArgs @("checkout", "main") | Out-Null
        }
    }

    $worktreePaths = Get-RepairWorktreeRoots -RepoRoot $repoRoot
    foreach ($path in $worktreePaths | Sort-Object -Unique) {
        Remove-RepairWorktree -WorktreePath $path -DryRun:$DryRun
    }

    Remove-OrphanWorktreeMetadata -RepoRoot $repoRoot -DryRun:$DryRun

    if ($DryRun) {
        Write-Host "[dry-run] Would run: git worktree prune -v"
    } else {
        Invoke-Git -GitArgs @("worktree", "prune", "-v") | Out-Null
        Remove-OrphanWorktreeMetadata -RepoRoot $repoRoot
    }

    $removedBranches = 0
    $orphanBranches = git branch --list "$RepairBranchPrefix*" | ForEach-Object { Get-GitBranchName $_ }
    foreach ($branch in $orphanBranches) {
        if (-not $branch) {
            continue
        }
        if ($DryRun) {
            Write-Host "[dry-run] Would delete branch: $branch"
            $removedBranches++
            continue
        }
        if ((Invoke-Git -GitArgs @("branch", "-D", $branch)) -eq 0) {
            $removedBranches++
        }
    }

    Write-Host ""
    Write-Host "Repair cleanup complete. Branches removed: $removedBranches."
    Write-Host "Remaining branches:"
    git branch
    Write-Host ""
    Write-Host "Worktrees:"
    git worktree list
}
finally {
    Pop-Location
}
