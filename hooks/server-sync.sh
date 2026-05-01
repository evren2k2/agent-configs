#!/bin/bash
VAULT="$HOME/obsidian_notes"
cd "$VAULT" || exit 1

LOG_FILE="$HOME/agent-configs/hooks/sync.log"

# Step 1: Commit local changes FIRST (so pull --rebase has a clean tree)
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    git add -A
    git commit -m "auto: $(date '+%Y-%m-%d %H:%M')"
fi

# Step 2: Pull remote changes
# Try to rebase first
if ! git pull --rebase origin main 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M'): PULL FAILED with rebase. Aborting rebase and trying merge with strategy 'ours'..." >> "$LOG_FILE"
    git rebase --abort 2>/dev/null
    
    # Try to merge, favoring local changes on conflict
    if ! git pull origin main --no-rebase -X ours --no-edit 2>&1; then
         echo "$(date '+%Y-%m-%d %H:%M'): MERGE FAILED. Manual intervention required." >> "$LOG_FILE"
         exit 1
    fi
fi

# Step 3: Push (local commits + any rebased/merged commits)
git push origin main 2>&1 || {
    echo "$(date '+%Y-%m-%d %H:%M'): PUSH FAILED" >> "$LOG_FILE"
    exit 1
}

echo "$(date '+%Y-%m-%d %H:%M'): Sync successful" >> "$LOG_FILE"
