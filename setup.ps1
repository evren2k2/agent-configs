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
    
    $items = @("settings.json", "CLAUDE.md", "GEMINI.md", "rules", "skills")
    
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

Write-Host "`nDone! Configuration links established." -ForegroundColor Green
Write-Host "`nNext Step: Setup your Obsidian Vault" -ForegroundColor Cyan
Write-Host "The configurations expect a vault at: $(Join-Path $HOME "obsidian_notes")"
Write-Host ""
Write-Host "Option A: Clone an existing vault repo:"
Write-Host "  git clone <your-repo-url> $(Join-Path $HOME "obsidian_notes")"
Write-Host ""
Write-Host "Option B: Initialize a fresh vault:"
Write-Host "  .\init-vault.ps1"

