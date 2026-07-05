#!/bin/bash
# PostToolUse hook: detect when instruction stack files are modified
# and remind to update corresponding vault documentation
INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', d)
    print(ti.get('file_path', ''))
except: pass
" 2>/dev/null)

[ -z "$FILE_PATH" ] && exit 0

VAULT="$HOME/obsidian_notes"
REMINDER=""

# Map: instruction stack files -> vault notes that document them
case "$FILE_PATH" in
    */.claude/CLAUDE.md|*/.claude/rules/obsidian-notes.md)
        REMINDER="You just modified an instruction stack file. Update your vault's system architecture notes if the change affects the documented architecture."
        ;;
    */skills/obsidian-notes/SKILL.md)
        REMINDER="You just modified the obsidian-notes skill. Update your vault's pattern and architecture documentation if behaviors changed."
        ;;
    */skills/obsidian-audit/SKILL.md)
        REMINDER="You just modified the obsidian-audit skill. Update vault audit criteria documentation if needed."
        ;;
    */.claude/settings.json)
        REMINDER="You just modified settings.json (hooks config). Ensure your vault's setup guide reflects these changes."
        ;;
    */agent-configs/hooks/*.sh)
        REMINDER="You just modified a hook script. Update your vault documentation if the core automation behavior changed."
        ;;
    */CLAUDE.md|*/GEMINI.md)
        # This matches project-level instructions
        REMINDER="You modified project instructions. Check if the vault's project context needs an update."
        ;;
esac


if [ -n "$REMINDER" ]; then
    # PostToolUse plain stdout is invisible to the model; emit additionalContext JSON.
    python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"STALE NOTE WARNING: "+sys.argv[1]}}))' "$REMINDER"
fi
