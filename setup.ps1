# setup.ps1 - Symlink agent configurations for Windows PowerShell
# Note: Requires Developer Mode or Administrative privileges for symlinks

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

Write-Host "Done! Configuration symlinks established." -ForegroundColor Green
