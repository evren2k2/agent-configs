#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT="$HOME/obsidian_notes"
cd "$VAULT" || exit 1

LOG_FILE="$SCRIPT_DIR/sync.log"

# Serialize cron runs: a 5-min cron can overlap a slow sync/embed and clash on
# git's index.lock or the vector store. Skip this run if another holds the lock.
exec 9>"$SCRIPT_DIR/.sync.lock"
flock -n 9 || { echo "$(date '+%Y-%m-%d %H:%M'): another sync running; skipping" >> "$LOG_FILE"; exit 0; }

# Cap the log so it can't grow unbounded.
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)" -gt 2000 ]; then
    tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

# Step 1: Commit local changes FIRST (so pull --rebase has a clean tree)
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    git add -A
    if ! git commit -q -m "auto: $(date '+%Y-%m-%d %H:%M')" >> "$LOG_FILE" 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M'): COMMIT FAILED — leaving tree for manual review" >> "$LOG_FILE"
        exit 1
    fi
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

# Step 4: refresh the semantic vector store (incremental, best-effort).
# Hashed change-detection means this is a near-instant no-op when nothing changed.
VAULT_CLI="$SCRIPT_DIR/../bin/vault"
if [ -f "$VAULT_CLI" ]; then
    for PY in python3 python py; do
        command -v "$PY" >/dev/null 2>&1 || continue
        "$PY" "$VAULT_CLI" embed >/dev/null 2>&1 || true
        break
    done
fi
