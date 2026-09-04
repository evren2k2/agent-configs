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

# Checkpoint headers are deliberately NOT listed here. The scan that used to build
# CHECKPOINT_LINES was dead code — computed on every session start, never emitted.
# To surface them, print `checkpoint.py list` output; to read one, the agent calls
# vault_checkpoint(project=...) on demand, which costs nothing until it is needed.

# --- Output (4-6 lines) ---
echo "Vault: ~/obsidian_notes/"
echo "Vault MCP tools (pre-approved, callable as mcp__vault-mcp__<name>): vault_project | vault_semantic_search | vault_find | vault_show | vault_links | vault_checkpoint"
echo "  A short name that does not resolve means the schema is unfetched, not that the tool is missing — fetch it, do not fall back to Read/Grep."
if [ -n "$MATCHED_PROJECT" ]; then
    echo "CWD project: $MATCHED_PROJECT"
    echo "Action: Call vault_project(name=\"$MATCHED_PROJECT\") to map this project's notes."
    if [ -f "$VAULT/projects/$MATCHED_PROJECT/working-context.md" ]; then
        echo "Last session: mcp__vault-mcp__vault_checkpoint(project=\"$MATCHED_PROJECT\") reads the last checkpoint verbatim"
        echo "              (fallback: python3 ~/.agent-configs/bin/checkpoint.py read --project $MATCHED_PROJECT)."
    fi
else
    echo "Action: Use vault_find or vault_project to locate project context."
fi

# --- Santa Method (surfaced only when a reviewer backend is configured) ---
# Gitignored, machine-local config (copied from the tracked santa-method.json.example).
SANTA_CONFIG="$HOME/.agent-configs/santa-method.json"
if [ -f "$SANTA_CONFIG" ] && grep -q '"command"' "$SANTA_CONFIG" 2>/dev/null; then
    echo "Santa Method: reviewer backend configured. For high-stakes output (RTL, verification infra, production scripts), invoke the santa-method skill and pass both reviewers before shipping."
fi
