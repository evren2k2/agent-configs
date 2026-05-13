# server-sync.ps1 - Synchronize Obsidian vault with remote repository
# Handles merge conflicts by favoring local changes

$VAULT = Join-Path $HOME "obsidian_notes"
$LOG_FILE = Join-Path $HOME "agent-configs\hooks\sync.log"

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
"----------------------------------------" | Add-Content $LOG_FILE
"${timestamp}: Starting sync attempt..." | Add-Content $LOG_FILE

if (-not (Test-Path $VAULT)) {
    "${timestamp}: ERROR - Vault path $VAULT not found." | Add-Content $LOG_FILE
    exit 1
}

Push-Location $VAULT

# Step 0: Handle stale git locks
$lockFile = Join-Path $VAULT ".git\index.lock"
if (Test-Path $lockFile) {
    $lockAge = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    if ($lockAge.TotalMinutes -gt 10) {
        "${timestamp}: Removing stale lock file ($($lockAge.TotalMinutes) mins old)" | Add-Content $LOG_FILE
        Remove-Item $lockFile -Force
    } else {
        "${timestamp}: ABORTING - Git lock file exists and is recent ($($lockAge.TotalMinutes) mins old)" | Add-Content $LOG_FILE
        Pop-Location
        exit 1
    }
}

# Step 1: Commit local changes FIRST
$status = git status --porcelain
if ($status) {
    git add -A
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "auto: $timestamp"
}

# Step 2: Pull remote changes
# Try to rebase first
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git pull --rebase origin main 2>&1 | Out-String | Set-Variable pullResult

if ($LASTEXITCODE -ne 0) {
    "${timestamp}: PULL FAILED with rebase. Aborting rebase and trying merge with strategy 'ours'..." | Add-Content $LOG_FILE
    git rebase --abort 2>$null
    
    # Try to merge, favoring local changes on conflict
    git pull origin main --no-rebase -X ours --no-edit 2>&1 | Out-String | Set-Variable mergeResult
    if ($LASTEXITCODE -ne 0) {
        "${timestamp}: MERGE FAILED. Manual intervention required." | Add-Content $LOG_FILE
        Pop-Location
        exit 1
    }
}

# Step 3: Push
git push origin main 2>&1 | Out-String | Set-Variable pushResult
if ($LASTEXITCODE -ne 0) {
    "${timestamp}: PUSH FAILED" | Add-Content $LOG_FILE
    Pop-Location
    exit 1
}

"${timestamp}: Sync successful" | Add-Content $LOG_FILE
Pop-Location
