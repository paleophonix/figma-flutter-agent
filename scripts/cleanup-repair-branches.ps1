# Remove local repair git worktrees and delete all repair/* branches.
# Cleans physical .worktrees/, orphaned .git/worktrees/* metadata, and stale repair/* refs.
# Does not touch remote branches or non-repair local branches (e.g. main).
param(
    [switch]$DryRun,
    [switch]$WaitForIdeExit,
    [switch]$RetryUntilRemoved,
    [int]$WaitTimeoutSec = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$RepairCaseIdPattern = '^\d{4}-\d{4}-'
$RepairBranchPrefix = "repair/"
$script:DeferredRemovals = [System.Collections.Generic.List[string]]::new()

function Get-EditorLockHints {
    # Cursor / VS Code open the repo. OpenAI Codex.exe is unrelated — do not wait on it.
    $names = @('Cursor', 'Code')
    return @(
        Get-Process -ErrorAction SilentlyContinue |
            Where-Object { $names -contains $_.ProcessName } |
            Select-Object -ExpandProperty ProcessName -Unique
    )
}

function Test-ShouldRetryRemovals {
    return $RetryUntilRemoved -or $WaitForIdeExit
}

function Wait-AndRemoveDirectory {
    param(
        [Parameter(Mandatory)][string]$Path,
        [int]$TimeoutSec
    )

    if (-not (Test-PathSafe -Path $Path)) {
        return $true
    }

    $deadline = [datetime]::UtcNow.AddSeconds($TimeoutSec)
    $attempt = 0
    while ([datetime]::UtcNow -lt $deadline) {
        $attempt++
        if (Remove-DirectoryForce -Path $Path -SuppressDeferred) {
            Write-Host "Removed locked directory on attempt ${attempt}: $Path"
            return $true
        }
        $editors = @(Get-EditorLockHints)
        $hint = if ($editors.Count -gt 0) {
            " (editors still running: $($editors -join ', '))"
        } else {
            ""
        }
        Write-Host "Directory still locked, retry ${attempt} in 2s: $Path$hint"
        Start-Sleep -Seconds 2
    }
    return -not (Test-PathSafe -Path $Path)
}

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

function Test-RegisteredWorktreePath {
    param([Parameter(Mandatory)][string]$WorktreePath)

    $normalized = $WorktreePath.TrimEnd('\', '/')
    foreach ($entry in Get-RegisteredWorktrees) {
        $registered = ([string]$entry.Path).TrimEnd('\', '/')
        if ($registered -ieq $normalized) {
            return $true
        }
    }
    return $false
}

function Test-UsableGitWorktreeDir {
    param([Parameter(Mandatory)][string]$WorktreePath)

    $gitMarker = Join-Path $WorktreePath ".git"
    return (Test-PathSafe -Path $gitMarker)
}

function Remove-DirectoryRobocopy {
    param([Parameter(Mandatory)][string]$Path)

    $empty = Join-Path ([System.IO.Path]::GetTempPath()) ("ffa-empty-" + [guid]::NewGuid().ToString("n"))
    try {
        New-Item -ItemType Directory -Path $empty -Force | Out-Null
        & robocopy $empty $Path /mir /r:0 /w:0 /nfl /ndl /njh /njs /np | Out-Null
        $code = $LASTEXITCODE
        if ($code -ge 8) {
            return $false
        }
        cmd /c "rmdir /s /q `"$Path`"" 2>$null | Out-Null
        return -not (Test-PathSafe -Path $Path)
    } finally {
        if (Test-PathSafe -Path $empty) {
            Remove-Item -LiteralPath $empty -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Remove-DirectoryForce {
    param(
        [Parameter(Mandatory)][string]$Path,
        [switch]$DryRun,
        [switch]$SuppressDeferred
    )

    if (-not (Test-PathSafe -Path $Path)) {
        return $true
    }
    if ($DryRun) {
        Write-Host "[dry-run] Would remove directory: $Path"
        return $true
    }
    try {
        cmd /c "attrib -R /S /D `"$Path\*`"" 2>$null | Out-Null
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        return $true
    } catch {
        # fall through to robocopy
    }

    if (Remove-DirectoryRobocopy -Path $Path) {
        return $true
    }

    if ($SuppressDeferred) {
        return $false
    }

    $editorHints = @(Get-EditorLockHints)
    $editorNote = if ($editorHints.Count -gt 0) {
        " Detected running editor: $($editorHints -join ', '). Fully quit Cursor (File -> Exit), then rerun with -RetryUntilRemoved."
    } else {
        ""
    }

    if (Test-PathSafe -Path $Path) {
        $script:DeferredRemovals.Add($Path)
        Write-Warning @"
Could not remove '$Path' (directory is locked by another process).$editorNote
If still blocked after quitting Cursor, reboot Windows.
"@
        return $false
    }
    return $true
}

function Resolve-DeferredRemovals {
    param([int]$TimeoutSec)

    if ($script:DeferredRemovals.Count -eq 0) {
        return
    }
    if (-not (Test-ShouldRetryRemovals)) {
        return
    }

    Write-Host ""
    Write-Host "Retrying $($script:DeferredRemovals.Count) locked path(s) for up to ${TimeoutSec}s..."
    $pending = @($script:DeferredRemovals)
    $script:DeferredRemovals.Clear()
    foreach ($path in $pending) {
        if (-not (Wait-AndRemoveDirectory -Path $path -TimeoutSec $TimeoutSec)) {
            $script:DeferredRemovals.Add($path)
        }
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

function Get-RepairWorktreeParentDirs {
    param([string]$RepoRoot)

    $paths = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

    $pythonExe = Join-Path $RepoRoot ".venv/Scripts/python.exe"
    if (-not (Test-PathSafe -Path $pythonExe)) {
        $pythonExe = "python"
    }
    $pythonCode = @"
import sys
from pathlib import Path
sys.path.insert(0, r'$RepoRoot\src')
from figma_flutter_agent.dev.opencode.worktree import worktree_parent_candidates
for path in worktree_parent_candidates(Path(r'$RepoRoot')):
    if path.is_dir():
        print(path)
"@
    try {
        $listed = & $pythonExe -c $pythonCode 2>$null
        foreach ($line in $listed) {
            $text = [string]$line
            if ($text) {
                [void]$paths.Add($text.Trim())
            }
        }
    } catch {
        # fall back to in-repo scan below
    }

    foreach ($parentName in @(".worktrees", ".repair/worktrees")) {
        $parent = Join-Path $RepoRoot $parentName
        if (Test-PathSafe -Path $parent) {
            [void]$paths.Add($parent)
        }
    }

    return @($paths)
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

    foreach ($parent in Get-RepairWorktreeParentDirs -RepoRoot $RepoRoot) {
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
        if (Test-RegisteredWorktreePath -WorktreePath $WorktreePath) {
            $code = Invoke-Git -GitArgs @("worktree", "remove", "--force", $WorktreePath)
            if ($code -ne 0) {
                Write-Warning "git worktree remove failed for $WorktreePath; removing directory directly."
                Remove-DirectoryForce -Path $WorktreePath | Out-Null
            }
        } else {
            Write-Host "Removing orphan worktree directory (not registered with git): $WorktreePath"
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
            if (-not (Test-RepairCaseId -Name $metaDir.Name)) {
                continue
            }
            $shouldRemove = $true
        } else {
            $worktreeRoot = $null
            if ($linkedGitFile) {
                $worktreeRoot = Split-Path -Parent $linkedGitFile
            }

            $isRepairMeta = Test-RepairCaseId -Name $metaDir.Name
            $linkedMissing = -not $linkedGitFile -or -not (Test-PathSafe -Path $linkedGitFile)
            $worktreeMissing = -not $worktreeRoot -or -not (Test-PathSafe -Path $worktreeRoot)
            $worktreeBroken = $false
            if ($worktreeRoot -and (Test-PathSafe -Path $worktreeRoot)) {
                $worktreeBroken = -not (Test-UsableGitWorktreeDir -WorktreePath $worktreeRoot)
            }
            $underAgentWorktrees = $false
            if ($worktreeRoot) {
                $underAgentWorktrees = (
                    $worktreeRoot -match '[\\/]\.worktrees[\\/]' -or
                    $worktreeRoot -match '[\\/]\.repair[\\/]worktrees[\\/]'
                )
            }

            $shouldRemove = $false
            if ($isRepairMeta -and ($linkedMissing -or $worktreeMissing -or $worktreeBroken)) {
                $shouldRemove = $true
            } elseif ($underAgentWorktrees -and ($linkedMissing -or $worktreeBroken)) {
                $shouldRemove = $true
            }
        }

        if (-not $shouldRemove) {
            continue
        }

        if ($DryRun) {
            Write-Host "[dry-run] Would remove orphaned worktree metadata: $($metaDir.Name)"
            continue
        }

        $removed = $false
        if (Test-ShouldRetryRemovals) {
            $removed = Wait-AndRemoveDirectory -Path $metaDir.FullName -TimeoutSec 120
        } else {
            $removed = Remove-DirectoryForce -Path $metaDir.FullName
        }
        if ($removed) {
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

    $editorHints = @(Get-EditorLockHints)
    if ($editorHints.Count -gt 0 -and -not $DryRun -and -not (Test-ShouldRetryRemovals)) {
        Write-Warning "Editor still running ($($editorHints -join ', ')). If cleanup fails, quit Cursor and rerun with -RetryUntilRemoved."
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
        $pythonExe = Join-Path $repoRoot ".venv/Scripts/python.exe"
        if (-not (Test-PathSafe -Path $pythonExe)) { $pythonExe = "python" }
        & $pythonExe -c "import sys; from pathlib import Path; sys.path.insert(0, r'$repoRoot\src'); from figma_flutter_agent.dev.opencode.worktree import prune_stale_git_worktree_registry; print(','.join(prune_stale_git_worktree_registry(Path(r'$repoRoot'))))" 2>$null | ForEach-Object {
            if ($_ -and $_ -ne '') { Write-Host "Pruned stale git worktree registry: $_" }
        }
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

    Resolve-DeferredRemovals -TimeoutSec $WaitTimeoutSec

    if ($script:DeferredRemovals.Count -gt 0) {
        Write-Warning "Deferred removals ($($script:DeferredRemovals.Count)) — quit Cursor and rerun with -RetryUntilRemoved, or reboot:"
        foreach ($deferred in $script:DeferredRemovals) {
            Write-Warning "  $deferred"
        }
    }
    Write-Host "Remaining branches:"
    Invoke-Git -GitArgs @("branch") | Out-Null
    Write-Host ""
    Write-Host "Worktrees:"
    Invoke-Git -GitArgs @("worktree", "list") | Out-Null
}
finally {
    Pop-Location
}
