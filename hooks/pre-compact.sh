#!/bin/bash

# Gemini uses different compacting logic than claude. Need to ensure that this hook is only called for manual compacts

# --- Capture Gemini CLI JSON Input ---
# Gemini sends a JSON payload to stdin. We read it to check why this hook fired.
INPUT=$(cat)

# Check if the trigger was automated by the agent loop.
# If it was "auto", we output a dummy success JSON and exit immediately to save resources.
if echo "$INPUT" | grep -q '"trigger": "auto"'; then
    echo '{"status": "skipped_auto"}'
    exit 0
fi

# Claude Code PreCompact hook: save snapshot to file, minimal output
# Keeps last 5 snapshots in file, outputs only checkpoint headers for recovery
# Hardened: all heavy ops wrapped in timeout, skip on failure, never hang.
VAULT="$HOME/obsidian_notes"
SNAPSHOT="$VAULT/agent/pre-compact-snapshot.md"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
SEPARATOR="---SNAPSHOT---"
GIT_TIMEOUT=3
FIND_TIMEOUT=3

# --- Build new snapshot entry (saved to file for future sessions) ---
ENTRY=$(cat <<ENTRY_EOF
$SEPARATOR
## Pre-Compact Snapshot — $TIMESTAMP

**CWD:** $PWD

### Git State
$(
    # Dynamically find repositories to check:
    # 1. The vault itself
    # 2. Sibling directories of the vault that match names in projects/
    REPOS="$VAULT"
    # Find Git repositories in HOME and see if they match a vault project
    for REPO_DIR in "$HOME"/*/; do
        [ -d "$REPO_DIR/.git" ] || continue
        REPO_NAME=$(basename "$REPO_DIR")
        MAPPED_NAME=$(echo "$REPO_NAME" | sed -e 's/ /-/g' -e 's/_/-/g' | tr '[:upper:]' '[:lower:]' | sed -e 's/--/-/g')
        if [ -d "$VAULT/projects/$MAPPED_NAME" ]; then
            REPOS="$REPOS $REPO_DIR"
        fi
    done

    for REPO in $REPOS; do
        if [ -d "$REPO/.git" ]; then
            REPO_NAME=$(basename "$REPO")
            BRANCH=$(timeout "$GIT_TIMEOUT" git -C "$REPO" branch --show-current 2>/dev/null) || continue
            CHANGES=$(timeout "$GIT_TIMEOUT" git -C "$REPO" diff --stat 2>/dev/null | tail -1)
            STAGED=$(timeout "$GIT_TIMEOUT" git -C "$REPO" diff --cached --stat 2>/dev/null | tail -1)
            RECENT_COMMITS=$(timeout "$GIT_TIMEOUT" git -C "$REPO" log --oneline -3 2>/dev/null)
            echo "**$REPO_NAME ($BRANCH):**"
            [ -n "$CHANGES" ] && echo "- Unstaged: $CHANGES"
            [ -n "$STAGED" ] && echo "- Staged: $STAGED"
            [ -z "$CHANGES" ] && [ -z "$STAGED" ] && echo "- Clean working tree"
            echo "- Recent commits:"
            echo "$RECENT_COMMITS" | sed 's/^/  - /'
            echo ""
        fi
    done
)

### Vault Notes Modified Today
$(timeout "$FIND_TIMEOUT" find "$VAULT" -name "*.md" -not -path "*/.git/*" -not -path "*/.obsidian/*" -newermt "$(date +%Y-%m-%d)" 2>/dev/null | head -10 || echo "(find timed out)")

ENTRY_EOF
)

# --- Keep last 5 snapshots in file ---
if [ -f "$SNAPSHOT" ]; then
    EXISTING=$(awk -v sep="$SEPARATOR" '
        BEGIN { idx=0; entry="" }
        $0 == sep {
            if (entry != "") { entries[idx++] = entry }
            entry = ""
            next
        }
        { entry = entry "\n" $0 }
        END {
            if (entry != "") { entries[idx++] = entry }
            start = (idx > 4) ? idx - 4 : 0
            for (i = start; i < idx; i++) {
                print sep
                print entries[i]
            }
        }
    ' "$SNAPSHOT")
    echo "$EXISTING" > "$SNAPSHOT"
    echo "$ENTRY" >> "$SNAPSHOT"
else
    echo "$ENTRY" > "$SNAPSHOT"
fi

# --- Minimal output: routed to STDERR (>&2) so it doesn't break Gemini's parser ---
echo "Compacted. Snapshot saved to vault." >&2
echo "" >&2

# List checkpoint headers
FOUND_ANY=""
for CTX in "$VAULT"/projects/*/working-context.md; do
    [ -f "$CTX" ] || continue
    PROJ=$(basename "$(dirname "$CTX")")
    while IFS= read -r line; do
        CLEAN=$(echo "$line" | sed 's/^## Checkpoint[ ]*[-—]*[ ]*//')
        echo "  $PROJ: $CLEAN" >&2
        FOUND_ANY="yes"
    done < <(grep "^## Checkpoint" "$CTX" 2>/dev/null)
done

if [ -n "$FOUND_ANY" ]; then
    echo "" >&2
    echo "Recovery: spawn a subagent to read the matching checkpoint from vault." >&2
    echo "Subagent reads full checkpoint, returns ~20-line summary to main context." >&2
else
    echo "No checkpoints found. Recover from git log + file reads." >&2
fi

# --- Final JSON Output for Gemini CLI Parser ---
echo '{"status": "success"}'