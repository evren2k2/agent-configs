#!/bin/bash
# Claude Code SessionStart hook: minimal bootstrap
# Agent loads deeper context via subagent when needed
VAULT="$HOME/obsidian_notes"
CWD="$PWD"

# --- Detect matching project by CWD name mapping ---
REPO_NAME=$(basename "$CWD")
MAPPED_NAME=$(echo "$REPO_NAME" | sed -e 's/ /-/g' -e 's/_/-/g' | tr '[:upper:]' '[:lower:]' | sed -e 's/--/-/g')
MATCHED_PROJECT=""

if [ -d "$VAULT/projects/$MAPPED_NAME" ]; then
    MATCHED_PROJECT="$MAPPED_NAME"
else
    # Fallback to keyword matching if explicit mapping fails
    for PROJECT_DIR in "$VAULT/projects"/*/; do
        [ -d "$PROJECT_DIR" ] || continue
        PROJECT_NAME=$(basename "$PROJECT_DIR")
        IFS='-' read -ra KEYWORDS <<< "$PROJECT_NAME"
        for KEYWORD in "${KEYWORDS[@]}"; do
            [ ${#KEYWORD} -lt 4 ] && continue
            if echo "$CWD" | grep -qi "$KEYWORD"; then
                MATCHED_PROJECT="$PROJECT_NAME"
                break 2
            fi
        done
    done
fi

# --- List checkpoint headers (one line each) ---
CHECKPOINT_LINES=""
for CTX in "$VAULT"/projects/*/working-context.md; do
    [ -f "$CTX" ] || continue
    PROJ=$(basename "$(dirname "$CTX")")
    while IFS= read -r line; do
        # Strip "## Checkpoint" prefix and any following dashes/spaces
        CLEAN=$(echo "$line" | sed 's/^## Checkpoint[ ]*[-—]*[ ]*//')
        CHECKPOINT_LINES+="  $PROJ: $CLEAN"$'\n'
    done < <(grep "^## Checkpoint" "$CTX" 2>/dev/null)
done

# --- Output (~4 lines) ---
echo "Vault: ~/obsidian_notes/"
if [ -n "$MATCHED_PROJECT" ]; then
    echo "CWD project: $MATCHED_PROJECT"
    echo "Action: Use the native 'vault_project' tool to explore this project."
else
    echo "Action: Use 'vault_find' or 'vault_project' to locate project context."
fi
