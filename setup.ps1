# setup.ps1 - Symlink agent configurations for Windows PowerShell
# Note: Requires Developer Mode or Administrative privileges for symlinks

# Check for Git Bash (required for .sh hooks on Windows)
if (-not (Get-Command bash -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'bash' not found in PATH." -ForegroundColor Red
    Write-Host "Git Bash is required to run the agent hooks on Windows." -ForegroundColor Red
    Write-Host "Please install Git for Windows: https://gitforwindows.org/" -ForegroundColor Cyan
    Write-Host "Ensure 'Git\bin' or 'Git\usr\bin' is added to your system PATH." -ForegroundColor Cyan
    exit 1
}

$REPO_DIR = $PSScriptRoot
$BACKUP_SUFFIX = ".orig." + (Get-Date -Format "yyyyMMdd_HHmmss")

function Setup-Links($agent) {
    Write-Host "===> Setting up $agent..." -ForegroundColor Cyan
    $target_dir = Join-Path $HOME ".$agent"
    
    if (-not (Test-Path $target_dir)) {
        New-Item -ItemType Directory -Path $target_dir | Out-Null
    }
    
    $items = @("settings.json", "CLAUDE.md", "GEMINI.md", "rules", "skills", "policies")
    
    foreach ($item in $items) {
        $src = Join-Path $REPO_DIR ".$agent\$item"
        $dest = Join-Path $target_dir $item
        
        if (-not (Test-Path $src)) { continue }
        
        $itemInfo = Get-Item -Path $dest -ErrorAction SilentlyContinue
        
        $isDir = (Get-Item -Path $src).PSIsContainer
        $linkType = if ($isDir) { "Junction" } else { "HardLink" }

        if ($null -ne $itemInfo -and $itemInfo.Attributes -match "ReparsePoint") {
            Write-Host "  [Skipping] $item (already a link)"
        }
        elseif (Test-Path $dest) {
            Write-Host "  [Backup] Moving existing $item to $item$BACKUP_SUFFIX" -ForegroundColor Yellow
            Rename-Item -Path $dest -NewName ($item + $BACKUP_SUFFIX)
            
            try {
                New-Item -ItemType SymbolicLink -Path $dest -Target $src -ErrorAction Stop | Out-Null
                Write-Host "  [Linking] $item (SymbolicLink)" -ForegroundColor Green
            } catch {
                New-Item -ItemType $linkType -Path $dest -Target $src | Out-Null
                Write-Host "  [Linking] $item ($linkType Fallback)" -ForegroundColor Yellow
            }
        }
        else {
            try {
                New-Item -ItemType SymbolicLink -Path $dest -Target $src -ErrorAction Stop | Out-Null
                Write-Host "  [Linking] $item (SymbolicLink)" -ForegroundColor Green
            } catch {
                New-Item -ItemType $linkType -Path $dest -Target $src | Out-Null
                Write-Host "  [Linking] $item ($linkType Fallback)" -ForegroundColor Yellow
            }
        }
    }
}

Setup-Links "claude"
Setup-Links "gemini"

# --- bin/ on PATH for the `vault` CLI ---------------------------------------
$binDir = Join-Path $REPO_DIR "bin"
if (Test-Path $binDir) {
    Write-Host "===> Ensuring $binDir is on User PATH..." -ForegroundColor Cyan
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -and ($userPath.Split(';') -contains $binDir)) {
        Write-Host "  [Skipping] $binDir already on User PATH"
    } else {
        $newPath = if ($userPath) { "$binDir;$userPath" } else { $binDir }
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "  [Added] $binDir to User PATH (open a new shell to pick it up)" -ForegroundColor Green
    }
    if (-not (Get-Command py -ErrorAction SilentlyContinue) -and `
        -not (Get-Command python3 -ErrorAction SilentlyContinue)) {
        Write-Host "  [Warning] Neither 'py' nor 'python3' found. The vault CLI requires Python 3.8+." -ForegroundColor Yellow
    }
}

# --- Semantic-search dependencies -------------------------------------------
# `vault embed` / vault_semantic_search need the packages in requirements.txt
# (sentence-transformers, numpy). The core vault CLI works without them.
Write-Host "===> Semantic-search dependencies..." -ForegroundColor Cyan
$reqFile = Join-Path $REPO_DIR "requirements.txt"
# Install target follows the cascade venv_bootstrap.py resolves at runtime:
# the repo venv, then the global venv, then the shell's Python.
$pipPy = $null
foreach ($venv in @((Join-Path $REPO_DIR ".venv"), (Join-Path $HOME ".venv"))) {
    $cand = Join-Path $venv "Scripts\python.exe"
    if (Test-Path $cand) { $pipPy = $cand; break }
}
if (-not $pipPy) {
    foreach ($c in @("py", "python3", "python")) {
        if (Get-Command $c -ErrorAction SilentlyContinue) { $pipPy = $c; break }
    }
}
$depsProbe = 'import importlib.util as u,sys; sys.exit(0 if u.find_spec("sentence_transformers") and u.find_spec("numpy") else 1)'
if (-not $pipPy) {
    Write-Host "  [Warning] no Python found — semantic search will be unavailable." -ForegroundColor Yellow
} else {
    & $pipPy -c $depsProbe 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] dependencies already present ($pipPy)" -ForegroundColor Green
    } else {
        Write-Host "  Installing into $pipPy ..."
        & $pipPy -m pip install --quiet -r $reqFile
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] semantic-search dependencies installed" -ForegroundColor Green
        } else {
            Write-Host "  [Warning] install failed — semantic search will be unavailable." -ForegroundColor Yellow
            Write-Host "            Fix your Python setup, then run:" -ForegroundColor Yellow
            Write-Host "              <python> -m pip install -r `"$reqFile`""
            Write-Host "            If the system Python is locked, create a venv at" -ForegroundColor Yellow
            Write-Host "              $REPO_DIR\.venv  (or ~\.venv)  and install there."
        }
    }
}

Write-Host "`nDone! Configuration links established." -ForegroundColor Green
Write-Host "`nNext Step: Setup your Obsidian Vault" -ForegroundColor Cyan
Write-Host "The configurations expect a vault at: $(Join-Path $HOME "obsidian_notes")"
Write-Host ""
Write-Host "Option A: Clone an existing vault repo:"
Write-Host "  git clone <your-repo-url> $(Join-Path $HOME "obsidian_notes")"
Write-Host ""
Write-Host "Option B: Initialize a fresh vault:"
Write-Host "  .\init-vault.ps1"

