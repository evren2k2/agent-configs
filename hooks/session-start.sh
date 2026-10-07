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
# Global learned dispositions: the user's rulings on how to work in EVERY project.
# They live in the vault, not the repo, and are printed here rather than installed as a
# rules file — there is no link step to forget. (agy does not run this hook yet: see the
# vault note agy-hooks-never-loaded.)
LD="$VAULT/agent/learned-dispositions.md"
if [ -f "$LD" ] && grep -q '^- ' "$LD"; then
    echo "LEARNED DISPOSITIONS — binding in every project (agent/learned-dispositions.md):"
    grep '^- ' "$LD" | head -25
fi
if [ -n "$MATCHED_PROJECT" ]; then
    echo "CWD project: $MATCHED_PROJECT"
    echo "Action: Call vault_project(name=\"$MATCHED_PROJECT\") to map this project's notes."
    if [ -f "$VAULT/projects/$MATCHED_PROJECT/working-context.md" ]; then
        echo "Last session: mcp__vault-mcp__vault_checkpoint(project=\"$MATCHED_PROJECT\") reads the last checkpoint verbatim"
        echo "              (fallback: python3 ~/.agent-configs/bin/checkpoint.py read --project $MATCHED_PROJECT)."
        echo "              Write checkpoints ONLY with \`checkpoint.py write\` — never append to working-context.md by hand."
    fi
    # Project working mode: the user's standing rulings on how THIS project is run
    # (agent role, tooling, process). Promoted project-scoped dispositions live here.
    # Printed verbatim because they must bind before the first action, and because on
    # 2026-09-21 the same rulings were lost when a checkpoint dropped its ledger.
    WM="$VAULT/projects/$MATCHED_PROJECT/decisions/working-mode.md"
    if [ -f "$WM" ]; then
        echo "WORKING MODE — binding for $MATCHED_PROJECT (projects/$MATCHED_PROJECT/decisions/working-mode.md; overrides generic hook lines below):"
        grep '^- ' "$WM" | head -25
    fi
else
    echo "Action: Use vault_find or vault_project to locate project context."
fi

# --- Dispositions awaiting the user's decision (silent when there are none) ---
# READY used to be visible only in the `propose` output of the turn it happened; if the
# agent did not ask then, nothing reminded anyone. Surface it at the start of every session.
timeout 5 python3 "$HOME/.agent-configs/bin/instincts.py" pending 2>/dev/null

# --- Cache keep-alive (Claude Code only: it needs CronCreate and Anthropic's prompt cache) ---
if [ -n "$CLAUDECODE" ]; then
    echo "Cache keep-alive: once per session — at the start of long or large-context work, or when launching a long-running shell/subagent — ask the user whether to keep the cache warm while they are away; if yes, use the cache-keepalive skill."
fi

# --- Santa Method (surfaced only when a reviewer backend is configured) ---
# Gitignored, machine-local config (copied from the tracked santa-method.json.example).
SANTA_CONFIG="$HOME/.agent-configs/santa-method.json"
if [ -f "$SANTA_CONFIG" ] && grep -q '"command"' "$SANTA_CONFIG" 2>/dev/null; then
    echo "Santa Method: reviewer backend configured. For high-stakes output (RTL, verification infra, production scripts), invoke the santa-method skill and pass both reviewers before shipping."
fi
